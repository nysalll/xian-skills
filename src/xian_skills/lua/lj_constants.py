# -*- coding: utf-8 -*-
"""Lightweight LuaJIT 2.0/2.1 bytecode constant dumper for decrypted .lua files."""

import re
import struct
from pathlib import Path

# BCDUMP constants from LuaJIT
BCDUMP_F_BE = 0x01
BCDUMP_F_STRIP = 0x02
BCDUMP_F_FFI = 0x04
BCDUMP_F_FR2 = 0x08

# Types
BCDUMP_KGC_CHILD = 0
BCDUMP_KGC_TAB = 1
BCDUMP_KGC_I64 = 2
BCDUMP_KGC_U64 = 3
BCDUMP_KGC_COMPLEX = 4
BCDUMP_KGC_STR = 5  # string with length (type - 5)


class Reader:
    def __init__(self, data: bytes):
        self.data = data
        self.p = 0

    def eof(self):
        return self.p >= len(self.data)

    def raw(self, n):
        b = self.data[self.p : self.p + n]
        self.p += n
        return b

    def byte(self):
        b = self.data[self.p]
        self.p += 1
        return b

    def uleb128(self):
        v = 0
        s = 0
        while True:
            b = self.byte()
            v |= (b & 0x7F) << s
            if b < 0x80:
                return v
            s += 7

    def uleb128_33(self):
        # LuaJIT uses a special 33-bit ULEB for numbers
        v = self.byte()
        if v >= 0x80:
            v &= 0x7F
            s = 7
            while True:
                b = self.byte()
                v |= (b & 0x7F) << s
                if b < 0x80:
                    break
                s += 7
        return v

    def string(self, n):
        return self.raw(n)


def dump_file(path: Path):
    data = path.read_bytes()
    if not data.startswith(b"\x1bLJ"):
        return {"error": "not luajit", "path": str(path)}

    r = Reader(data)
    r.raw(3)  # magic
    version = r.byte()
    flags = r.byte()
    result = {
        "file": str(path),
        "version": version,
        "flags": flags,
        "chunkname": None,
        "strings": [],
        "numbers": [],
        "tables": [],
        "raw_strings_fallback": [],
    }

    # chunk name length (unless STRIP)
    if not (flags & BCDUMP_F_STRIP):
        namelen = r.uleb128()
        if namelen:
            result["chunkname"] = r.string(namelen).decode("utf-8", "ignore")

    # Prototype stream: each proto prefixed by length ULEB; 0 length ends
    protos = []
    try:
        while not r.eof():
            size = r.uleb128()
            if size == 0:
                break
            start = r.p
            end = start + size
            proto_data = r.data[start:end]
            r.p = end
            protos.append(parse_proto(proto_data, flags, version))
    except Exception as e:
        result["parse_error"] = str(e)
        # fallback strings
        result["raw_strings_fallback"] = extract_fallback_strings(data)

    result["protos"] = protos
    # flatten
    for pr in protos:
        result["strings"].extend(pr.get("strings", []))
        result["numbers"].extend(pr.get("numbers", []))
        result["tables"].extend(pr.get("tables", []))
    return result


def parse_proto(data: bytes, flags: int, version: int):
    r = Reader(data)
    out = {"strings": [], "numbers": [], "tables": [], "kgc": []}
    try:
        flags_p = r.byte()
        numparams = r.byte()
        framesize = r.byte()
        sizeuv = r.byte()
        sizekgc = r.uleb128()
        sizekn = r.uleb128()
        sizebc = r.uleb128()
        out["meta"] = {
            "flags": flags_p,
            "numparams": numparams,
            "framesize": framesize,
            "sizeuv": sizeuv,
            "sizekgc": sizekgc,
            "sizekn": sizekn,
            "sizebc": sizebc,
        }
        sizedbg = 0
        if not (flags & BCDUMP_F_STRIP):
            sizedbg = r.uleb128()
            if sizedbg:
                firstline = r.uleb128()
                numline = r.uleb128()
                out["meta"]["firstline"] = firstline
                out["meta"]["numline"] = numline

        # bytecode instructions
        bc = r.raw(sizebc * 4)

        # upvalues
        uv = r.raw(sizeuv * 2)

        # kgc constants (complex / GC objects) — reverse order in dump
        kgcs = []
        for _ in range(sizekgc):
            t = r.uleb128()
            if t >= BCDUMP_KGC_STR:
                slen = t - BCDUMP_KGC_STR
                s = r.string(slen).decode("utf-8", "ignore")
                kgcs.append(("str", s))
                out["strings"].append(s)
            elif t == BCDUMP_KGC_TAB:
                tab = read_table(r)
                kgcs.append(("tab", tab))
                out["tables"].append(tab)
            elif t == BCDUMP_KGC_I64:
                kgcs.append(("i64", r.raw(8)))
            elif t == BCDUMP_KGC_U64:
                kgcs.append(("u64", r.raw(8)))
            elif t == BCDUMP_KGC_COMPLEX:
                kgcs.append(("complex", r.raw(16)))
            elif t == BCDUMP_KGC_CHILD:
                kgcs.append(("child", None))
            else:
                kgcs.append(("unk", t))
        out["kgc"] = [{"type": a, "val": b if a != "tab" else b} for a, b in kgcs]

        # numeric constants
        for _ in range(sizekn):
            # lo = uleb128_33; if odd => integer (lo>>1), else number (lo>>1 + hi as double bits)
            lo = r.uleb128_33()
            if lo & 1:
                num = lo >> 1
                out["numbers"].append(num)
            else:
                hi = r.uleb128()
                low32 = lo >> 1
                bits = (hi << 32) | low32
                num = struct.unpack("<d", struct.pack("<Q", bits))[0]
                out["numbers"].append(num)

        # debug info skip
        if sizedbg:
            r.raw(sizedbg)

    except Exception as e:
        out["error"] = str(e)
        out["strings"].extend(extract_fallback_strings(data))
    return out


def read_table(r: Reader):
    narray = r.uleb128()
    nhash = r.uleb128()
    arr = []
    for _ in range(narray):
        arr.append(read_ktabk(r))
    hashmap = []
    for _ in range(nhash):
        k = read_ktabk(r)
        v = read_ktabk(r)
        hashmap.append((k, v))
    return {"array": arr, "hash": hashmap}


def read_ktabk(r: Reader):
    # ktab const type
    t = r.uleb128()
    # 0 nil, 1 false, 2 true, 3 int, 4 num, >=5 str
    if t == 0:
        return None
    if t == 1:
        return False
    if t == 2:
        return True
    if t == 3:
        return r.uleb128()
    if t == 4:
        lo = r.uleb128()
        hi = r.uleb128()
        bits = (hi << 32) | lo
        return struct.unpack("<d", struct.pack("<Q", bits))[0]
    slen = t - 5
    return r.string(slen).decode("utf-8", "ignore")


def extract_fallback_strings(data: bytes):
    out = []
    for m in re.finditer(rb"[\x20-\x7e]{3,}", data):
        out.append(m.group().decode("ascii"))
    for m in re.finditer(rb"(?:[\xE4-\xE9][\x80-\xBF]{2}){2,}", data):
        try:
            out.append(m.group().decode("utf-8"))
        except Exception:
            pass
    return out


def to_jsonable(obj):
    if isinstance(obj, dict):
        return {str(k): to_jsonable(v) for k, v in obj.items()}
    if isinstance(obj, (list, tuple)):
        return [to_jsonable(x) for x in obj]
    if isinstance(obj, bytes):
        return obj.hex()
    return obj

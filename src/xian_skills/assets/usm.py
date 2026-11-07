"""Demux CRI USM containers into IVF video and raw audio streams."""

from __future__ import annotations

import os
import struct
import time

SIG_EXT = {b"@SFV": ".ivf", b"@ALP": "_alpha.m2v"}
ALIGN = 0x20


def _extract_ivf(data: bytes, chunks) -> bytes:
    out = bytearray()
    started = False
    for payload_at, size, header_size in chunks:
        head = data[payload_at : payload_at + 4]
        if head == b"@UTF" or head[:1] == b"#":
            continue
        if head == b"DKIF":
            out.extend(data[payload_at : payload_at + 32])
            pos = payload_at + 32
            end = payload_at + (size - 8 - header_size) + 8
            while pos + 12 <= end:
                frame_size = struct.unpack("<I", data[pos : pos + 4])[0]
                if frame_size > 64 * 1024 * 1024:
                    break
                out.extend(data[pos : pos + 12 + frame_size])
                pos += 12 + frame_size
            started = True
        elif started:
            frame_size = struct.unpack("<I", data[payload_at : payload_at + 4])[0]
            if frame_size > 64 * 1024 * 1024:
                continue
            out.extend(data[payload_at : payload_at + 12 + frame_size])
    return bytes(out) if started else b""


def demux_one(usm_path: str, out_dir: str) -> dict:
    name = os.path.splitext(os.path.basename(usm_path))[0]
    result = {"file": os.path.basename(usm_path), "status": "ok", "error": None, "outputs": [], "chunks": 0}
    started = time.time()
    try:
        with open(usm_path, "rb") as handle:
            data = handle.read()
        streams = {b"@SFV": [], b"@ALP": [], b"@SFA": []}
        offset = 0
        size_total = len(data)
        while offset + 8 <= size_total:
            sig = data[offset : offset + 4]
            size = struct.unpack(">I", data[offset + 4 : offset + 8])[0]
            if (sig[:1] != b"@" and sig != b"CRID") or size < 8 or offset + size > size_total:
                offset += ALIGN
                continue
            header_size = struct.unpack(">H", data[offset + 8 : offset + 10])[0]
            if sig in streams and 8 + header_size <= size:
                streams[sig].append((offset + 8 + header_size, size, header_size))
                result["chunks"] += 1
            offset = (offset + size + ALIGN - 1) & ~(ALIGN - 1)
        os.makedirs(out_dir, exist_ok=True)
        wrote = False
        for sig, chunks in streams.items():
            if not chunks:
                continue
            if sig == b"@SFA":
                buf = b"".join(data[at : at + size - 8 - header] for at, size, header in chunks)
                ext = ".adx" if buf[:2] == b"\x80\x00" else (".hca" if buf[:4] == b"HCA\x00" else ".bin")
                out_name = name + ext
            elif sig == b"@ALP":
                parts = []
                for at, size, header in chunks:
                    head = data[at : at + 4]
                    if head == b"@UTF" or head[:1] == b"#":
                        continue
                    parts.append(data[at : at + size - 8 - header])
                buf = b"".join(parts)
                if not buf:
                    continue
                out_name = name + SIG_EXT[sig]
            else:
                buf = _extract_ivf(data, chunks)
                if not buf:
                    continue
                out_name = name + SIG_EXT[sig]
            out_path = os.path.join(out_dir, out_name)
            with open(out_path, "wb") as handle:
                handle.write(buf)
            result["outputs"].append({"name": out_name, "size": len(buf)})
            wrote = True
        if not wrote:
            result["status"] = "empty"
            result["error"] = "未找到可提取的媒体流"
    except Exception as exc:
        result["status"] = "error"
        result["error"] = f"{type(exc).__name__}: {exc}"
    result["elapsed"] = round(time.time() - started, 3)
    return result

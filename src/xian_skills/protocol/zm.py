# -*- coding: utf-8 -*-
"""pcap to IPv4/IPv6 to TCP/UDP.

Decodes frames from a pcap the user recorded on their own device.
It does not contact a game server.

游戏服是裸 TCP。帧头 10 字节：ZM + 大端 uint32 时间戳 + 大端 uint32 长度，
后面是 msgpack [消息名, 参数]。login / sync_server_time 之后，客户端上行是
"cr" + AES-128-ECB。截断必须按 IP 总长度，链路层填充不算载荷。
"""
from __future__ import annotations

import json
import re
import struct
from collections import Counter, defaultdict

import msgpack

try:
    from Crypto.Cipher import AES
except Exception:  # pragma: no cover - optional at import
    AES = None

MAGIC_US = 0xA1B2C3D4
MAGIC_NS = 0xA1B23C4D
LINK_ETHER = 1
LINK_SLL = 113
LINK_SLL2 = 276
MAGIC = b"ZM"
MAX_BODY = 1024 * 1024
MAX_FLOW = 32 * 1024 * 1024
_IP_TYPES = {0x0800, 0x86DD}
_V6_EXT = {0, 43, 60}
_SERVER_PORTS = {53, 80, 123, 443, 853, 8080, 8443}
_RID_RE = re.compile(r"^[A-Za-z][0-9A-Za-z]{16}$")
_HTTP_START = (b"GET ", b"POST", b"PUT ", b"HEAD", b"HTTP")

PROFILES = {
    "full": None,
    "mijing": frozenset({"appear", "skill_hit", "attrib_update"}),
    "pvp": frozenset(
        {
            "show_battle_start",
            "player_pk_op",
            "trigger_combat",
            "appear",
            "die",
            "skill_hit",
            "skill_dodge",
            "skill_cast",
            "special_skill_cast",
            "status_update",
            "special_combat_log",
            "combat_field_update",
            "field_update",
            "attrib_update",
        }
    ),
    "combat": frozenset(
        {
            "show_battle_start",
            "player_pk_op",
            "trigger_combat",
            "appear",
            "die",
            "skill_hit",
            "skill_dodge",
            "skill_cast",
            "special_skill_cast",
            "status_update",
            "special_combat_log",
            "combat_field_update",
            "field_update",
            "attrib_update",
        }
    ),
}


def is_local_ip(ip):
    if not ip or ":" in ip:
        low = (ip or "").lower()
        return low == "::1" or low.startswith("fe80:") or low.startswith("fc") or low.startswith("fd")
    parts = ip.split(".")
    if len(parts) != 4:
        return False
    try:
        a, b = int(parts[0]), int(parts[1])
    except ValueError:
        return False
    if a == 10 or a == 127:
        return True
    if a == 192 and b == 168:
        return True
    if a == 172 and 16 <= b <= 31:
        return True
    return False


def _endpoint(ip, port):
    if ":" in ip:
        return f"[{ip}]:{port}"
    return f"{ip}:{port}"


def _conn(src, sport, dst, dport):
    a = (src, sport)
    b = (dst, dport)
    return (a, b) if a <= b else (b, a)


def _as_int(value):
    if isinstance(value, bool):
        return None
    if isinstance(value, int):
        return value
    if isinstance(value, float) and value.is_integer():
        return int(value)
    return None


def _key_bytes(time_val, rid):
    if not isinstance(rid, str) or len(rid) < 9:
        return None
    raw = f"{int(time_val)}{rid[3:9]}".encode()
    if len(raw) not in (16, 24, 32):
        return None
    return raw


def _unpad(buf):
    if len(buf) < 8 or len(buf) % 16 != 0:
        return None
    if buf[0] != buf[2] or buf[1] != buf[3]:
        return None
    length = struct.unpack(">I", buf[4:8])[0]
    if length > len(buf) - 8:
        return None
    return buf[8 : 8 + length]


def _decrypt_msg(key, body):
    if AES is None or not key or not body.startswith(b"cr"):
        return None
    raw = body[2:]
    if not raw or len(raw) % 16:
        return None
    try:
        plain = AES.new(key, AES.MODE_ECB).decrypt(raw)
    except Exception:
        return None
    data = _unpad(plain)
    if not data:
        return None
    try:
        msg = msgpack.unpackb(data, raw=False, strict_map_key=False)
    except Exception:
        return None
    if isinstance(msg, list) and msg and isinstance(msg[0], str):
        return msg
    return None


def decode_payload(payload):
    if payload[:2] == b"cr":
        return {"_encrypted": True, "len": len(payload)}
    try:
        return msgpack.unpackb(payload, raw=False, strict_map_key=False)
    except Exception as exc:
        return {"_raw_hex": payload[:64].hex(), "_err": str(exc), "_len": len(payload)}


def _game_body(body):
    if body.startswith(b"cr") and len(body) >= 18 and (len(body) - 2) % 16 == 0:
        return True
    try:
        msg = msgpack.unpackb(body, raw=False, strict_map_key=False)
    except Exception:
        return False
    if isinstance(msg, str):
        return msg in ("ping", "pong")
    return isinstance(msg, list) and bool(msg) and isinstance(msg[0], str) and 1 <= len(msg[0]) <= 80


def _is_tls(hint):
    return (
        len(hint) >= 3
        and hint[0] in (0x14, 0x15, 0x16, 0x17)
        and hint[1] == 0x03
        and hint[2] in (0x01, 0x02, 0x03, 0x04)
    )


def _boundary(blob, end):
    n = len(blob)
    if end == n:
        return True
    if end > n:
        return False
    nxt = blob[end : end + 2]
    if nxt == MAGIC:
        return True
    return len(nxt) < 2 and (not nxt or nxt == b"Z")


def _l3(linktype, data):
    if linktype == LINK_SLL2:
        if len(data) < 20 or struct.unpack(">H", data[0:2])[0] not in _IP_TYPES:
            return None
        return data[20:]
    if linktype == LINK_SLL:
        if len(data) < 16 or struct.unpack(">H", data[14:16])[0] not in _IP_TYPES:
            return None
        return data[16:]
    if linktype == LINK_ETHER:
        if len(data) < 14:
            return None
        proto = struct.unpack(">H", data[12:14])[0]
        off = 14
        if proto == 0x8100 and len(data) >= 18:
            proto = struct.unpack(">H", data[16:18])[0]
            off = 18
        if proto not in _IP_TYPES:
            return None
        return data[off:]
    return None


def _ipv6_str(raw):
    parts = [struct.unpack(">H", raw[i : i + 2])[0] for i in range(0, 16, 2)]
    best = (-1, -1)
    i = 0
    while i < 8:
        if parts[i] != 0:
            i += 1
            continue
        j = i
        while j < 8 and parts[j] == 0:
            j += 1
        if j - i > best[1] - best[0]:
            best = (i, j)
        i = j
    if best[1] - best[0] < 2:
        return ":".join(f"{p:x}" for p in parts)
    a, b = best
    left = ":".join(f"{p:x}" for p in parts[:a])
    right = ":".join(f"{p:x}" for p in parts[b:])
    return f"{left}::{right}"


def _ipv4(data):
    if len(data) < 20 or data[0] >> 4 != 4:
        return None
    ihl = (data[0] & 0x0F) * 4
    if ihl < 20 or len(data) < ihl:
        return None
    total = struct.unpack(">H", data[2:4])[0]
    if total < ihl:
        return None
    frag = struct.unpack(">H", data[6:8])[0]
    if frag & 0x3FFF:
        return None
    end = min(len(data), total)
    src = ".".join(map(str, data[12:16]))
    dst = ".".join(map(str, data[16:20]))
    return data[9], src, dst, data[ihl:end]


def _ipv6(data):
    if len(data) < 40 or data[0] >> 4 != 6:
        return None
    payload_len = struct.unpack(">H", data[4:6])[0]
    nh = data[6]
    off = 40
    end = min(len(data), 40 + payload_len)
    while nh in _V6_EXT and off + 2 <= end:
        nxt = data[off]
        step = (data[off + 1] + 1) * 8
        if off + step > end:
            return None
        nh = nxt
        off += step
    if nh not in (6, 17) or off > end:
        return None
    return nh, _ipv6_str(data[8:24]), _ipv6_str(data[24:40]), data[off:end]


def _ip(data):
    if not data:
        return None
    version = data[0] >> 4
    if version == 4:
        return _ipv4(data)
    if version == 6:
        return _ipv6(data)
    return None


def _tcp(data):
    if len(data) < 20:
        return None
    sport, dport, seq = struct.unpack(">HHI", data[:8])
    off = (data[12] >> 4) * 4
    if off < 20 or len(data) < off:
        return None
    return sport, dport, seq, data[off:]


def _udp(data):
    if len(data) < 8:
        return None
    sport, dport, length = struct.unpack(">HHH", data[:6])
    if length < 8:
        return None
    end = min(len(data), length)
    return sport, dport, data[8:end]


def parse_tcp_packet(linktype, raw):
    rest = _l3(linktype, raw)
    if rest is None:
        return None
    ip = _ip(rest)
    if ip is None or ip[0] != 6:
        return None
    tcp = _tcp(ip[3])
    if tcp is None or not tcp[3]:
        return None
    sport, dport, seq, payload = tcp
    return ip[1], sport, ip[2], dport, seq, payload


def parse_sni(data):
    if len(data) < 5 or data[0] != 0x16:
        return None
    rec_len = struct.unpack(">H", data[3:5])[0]
    hs = data[5 : 5 + rec_len]
    if len(hs) < 42 or hs[0] != 1:
        return None
    i = 38
    if i >= len(hs):
        return None
    sid_len = hs[i]
    i += 1 + sid_len
    if i + 2 > len(hs):
        return None
    cs_len = struct.unpack(">H", hs[i : i + 2])[0]
    i += 2 + cs_len
    if i >= len(hs):
        return None
    comp_len = hs[i]
    i += 1 + comp_len
    if i + 2 > len(hs):
        return None
    ext_len = struct.unpack(">H", hs[i : i + 2])[0]
    i += 2
    end = min(len(hs), i + ext_len)
    while i + 4 <= end:
        et, el = struct.unpack(">HH", hs[i : i + 4])
        i += 4
        if i + el > end:
            break
        if et == 0 and el >= 5:
            name_len = struct.unpack(">H", hs[i + 3 : i + 5])[0]
            name = hs[i + 5 : i + 5 + name_len]
            if name:
                return name.decode("utf-8", "replace")
        i += el
    return None


def parse_http_head(data):
    raw = bytes(data[:4096])
    line, _, rest = raw.partition(b"\r\n")
    text = line.decode("latin1", "replace")[:240]
    parts = text.split(" ")
    info = {"line": text}
    if parts and parts[0].startswith("HTTP/") and len(parts) >= 2:
        info["status"] = parts[1]
    elif len(parts) >= 2:
        info["method"] = parts[0]
        info["target"] = parts[1][:300]
    for row in rest.split(b"\r\n"):
        if not row:
            break
        if row.lower().startswith(b"host:"):
            info["host"] = row.split(b":", 1)[1].strip().decode("latin1", "replace")[:200]
            break
    return info


def read_pcap_header(fp):
    gh = fp.read(24)
    if len(gh) < 24:
        raise ValueError("pcap header truncated")
    magic = struct.unpack("<I", gh[:4])[0]
    if magic not in (MAGIC_US, MAGIC_NS):
        raise ValueError(f"bad pcap magic {magic:#x}")
    linktype = struct.unpack("<I", gh[20:24])[0]
    return linktype, magic == MAGIC_NS


def iter_pcap_packets(fp, linktype, ns):
    while True:
        ph = fp.read(16)
        if len(ph) < 16:
            break
        ts_sec, ts_frac, incl, _orig = struct.unpack("<IIII", ph)
        data = fp.read(incl)
        if len(data) < incl:
            break
        ts = ts_sec + (ts_frac / 1e9 if ns else ts_frac / 1e6)
        yield ts, data, linktype


def iter_pcap_file(path):
    with open(path, "rb") as fp:
        linktype, ns = read_pcap_header(fp)
        yield from iter_pcap_packets(fp, linktype, ns)


def _ts_at(marks, off, fallback):
    if not marks:
        return fallback
    t = marks[0][1]
    for end, ts in marks:
        if end >= off:
            return ts
        t = ts
    return t


def _walk_rids(obj, found):
    if isinstance(obj, str):
        if _RID_RE.match(obj):
            found.add(obj)
        return
    if isinstance(obj, list):
        for item in obj:
            _walk_rids(item, found)
        return
    if isinstance(obj, dict):
        for item in obj.values():
            _walk_rids(item, found)


class _Keys:
    def __init__(self):
        self.rid = None
        self.times = []
        self.cands = set()

    def note_rid(self, rid):
        if isinstance(rid, str) and len(rid) >= 9:
            self.rid = rid

    def note_time(self, ts, conn, time_val):
        if isinstance(time_val, int):
            self.times.append((ts, conn, time_val))

    def note_msg(self, msg):
        if self.rid or not isinstance(msg, list) or not msg:
            return
        found = set()
        _walk_rids(msg, found)
        if len(self.cands) < 4000:
            self.cands.update(found)

    def learn(self, msg, ts, conn):
        if not isinstance(msg, list) or not msg or not isinstance(msg[0], str):
            self.note_msg(msg)
            return
        mid = msg[0]
        args = msg[1] if len(msg) > 1 else None
        if mid == "sync_server_time":
            if isinstance(args, list) and args:
                time_val = _as_int(args[0])
            else:
                time_val = _as_int(args)
            if time_val is not None:
                self.note_time(ts, conn, time_val)
        elif mid == "login" and isinstance(args, list) and args:
            if isinstance(args[0], dict):
                rid = args[0].get("role_id") or args[0].get("rid")
                if isinstance(rid, str):
                    self.note_rid(rid)
            elif isinstance(args[0], str):
                self.note_rid(args[0])
                if len(args) >= 3:
                    time_val = _as_int(args[2])
                    if time_val is not None:
                        self.note_time(ts, conn, time_val)
        self.note_msg(msg)

    def time_for(self, ts, conn):
        best_ts = None
        best = None
        for event_ts, event_conn, time_val in self.times:
            if event_conn != conn or event_ts > ts:
                continue
            if best_ts is None or event_ts >= best_ts:
                best_ts = event_ts
                best = time_val
        return best

    def key_at(self, ts, conn):
        if not self.rid:
            return None
        time_val = self.time_for(ts, conn)
        if time_val is None:
            return None
        return _key_bytes(time_val, self.rid)

    def try_lock(self, samples):
        if self.rid or not self.cands or not samples or AES is None:
            return
        probe = []
        for item in samples:
            if self.time_for(item["ts"], item["conn"]) is not None:
                probe.append(item)
            if len(probe) >= 8:
                break
        if not probe:
            return
        best = None
        best_hit = 0
        for rid in self.cands:
            hit = 0
            for item in probe:
                time_val = self.time_for(item["ts"], item["conn"])
                key = _key_bytes(time_val, rid)
                if key and _decrypt_msg(key, item["body"]) is not None:
                    hit += 1
            if hit > best_hit:
                best_hit = hit
                best = rid
                if hit == len(probe) and len(probe) >= 2:
                    break
        if best and best_hit:
            self.rid = best
            self.cands.clear()


class Flow:
    __slots__ = (
        "base",
        "buf",
        "have",
        "marks",
        "aligned",
        "game",
        "nbytes",
        "reported",
        "last_ts",
        "sni",
        "http",
        "hint",
        "gaps",
    )

    def __init__(self):
        self.base = None
        self.buf = bytearray()
        self.have = bytearray()
        self.marks = []
        self.aligned = False
        self.game = False
        self.nbytes = 0
        self.reported = 0
        self.last_ts = 0.0
        self.sni = None
        self.http = None
        self.hint = None
        self.gaps = 0

    def push(self, seq, payload, ts):
        if not payload:
            return
        self.nbytes += len(payload)
        self.last_ts = ts
        if self.hint is None:
            self.hint = payload[:5]
        if self.sni is None and payload[:1] == b"\x16":
            self.sni = parse_sni(payload)
        if self.http is None and payload[:4] in _HTTP_START:
            self.http = parse_http_head(payload)
        self._add(seq, payload, ts)

    def _add(self, seq, data, ts):
        if self.base is None:
            self.base = seq
        off = (seq - self.base) & 0xFFFFFFFF
        if off > 0x80000000:
            back = (self.base - seq) & 0xFFFFFFFF
            if back >= len(data):
                return
            data = data[back:]
            off = 0
        if off > MAX_FLOW:
            self.gaps += 1
            self.aligned = False
            self.base = seq
            self.buf = bytearray(data)
            self.have = bytearray(b"\x01" * len(data))
            self.marks = [(len(data), ts)]
            return
        end = off + len(data)
        if end > len(self.buf):
            grow = end - len(self.buf)
            self.buf.extend(b"\x00" * grow)
            self.have.extend(b"\x00" * grow)
        self.buf[off:end] = data
        self.have[off:end] = b"\x01" * len(data)
        self.marks.append((end, ts))

    def _contig(self):
        n = 0
        limit = len(self.have)
        while n < limit and self.have[n]:
            n += 1
        return n

    def _discard(self, count):
        if count <= 0:
            return
        del self.buf[:count]
        del self.have[:count]
        self.base = (self.base + count) & 0xFFFFFFFF
        self.marks = [(end - count, ts) for end, ts in self.marks if end > count]

    def _discard_hole(self):
        i = 0
        while i < len(self.have) and not self.have[i]:
            i += 1
        if i <= 0:
            return False
        self.gaps += 1
        self.aligned = False
        self._discard(i)
        return True

    def _scan(self, blob):
        frames = []
        i = 0
        n = len(blob)
        aligned = self.aligned
        while i + 10 <= n:
            if blob[i : i + 2] != MAGIC:
                if aligned:
                    aligned = False
                j = blob.find(MAGIC, i + 1)
                if j < 0:
                    keep = 1 if blob[-1:] == b"Z" else 0
                    self.aligned = aligned
                    return frames, n - keep, False
                i = j
            length = struct.unpack(">I", blob[i + 6 : i + 10])[0]
            if length > MAX_BODY:
                aligned = False
                i += 2
                continue
            end = i + 10 + length
            if end > n:
                self.aligned = aligned
                return frames, i, True
            if not _boundary(blob, end):
                aligned = False
                i += 2
                continue
            body = blob[i + 10 : end]
            if not aligned and not _game_body(body):
                i += 2
                continue
            stamp = struct.unpack(">I", blob[i + 2 : i + 6])[0]
            frames.append((stamp, body, _ts_at(self.marks, end, self.last_ts)))
            aligned = True
            i = end
        self.aligned = aligned
        return frames, i, False

    def take_frames(self):
        frames = []
        while True:
            n = self._contig()
            if n < 10 and n == len(self.buf):
                break
            blob = bytes(self.buf[:n])
            got, consume, hold = self._scan(blob)
            if got:
                self.game = True
                frames.extend(got)
            if consume:
                self._discard(consume)
            if hold:
                if self._contig() < len(self.buf):
                    self.aligned = False
                    self._discard(self._contig())
                    self._discard_hole()
                    continue
                break
            if self._contig() < len(self.buf):
                self._discard_hole()
                continue
            break
        return frames


class Assembler:
    def __init__(self, keep=None):
        self.flows = {}
        self.keep = keep
        self.ip_flows = defaultdict(set)
        self.frames = 0
        self.kept = 0
        self.decrypted = 0
        self.still_encrypted = 0
        self.side_n = 0
        self.gaps = 0
        self.by_msg = Counter()
        self.keys = _Keys()
        self.pending = []
        self.udp = []

    def _dir(self, src, sport, dst, dport):
        sl, dl = is_local_ip(src), is_local_ip(dst)
        if sl and not dl:
            return "c2s"
        if dl and not sl:
            return "s2c"
        if dport in _SERVER_PORTS and sport not in _SERVER_PORTS:
            return "c2s"
        if sport in _SERVER_PORTS and dport not in _SERVER_PORTS:
            return "s2c"
        local = max(self.ip_flows, key=lambda ip: len(self.ip_flows[ip]), default=None)
        return "c2s" if src == local else "s2c"

    def _flow_name(self, src, sport, dst, dport):
        return f"{_endpoint(src, sport)}->{_endpoint(dst, dport)}"

    def ingest(self, ts, raw, linktype):
        rest = _l3(linktype, raw)
        if rest is None:
            return []
        ip = _ip(rest)
        if ip is None:
            return []
        proto, src, dst, segment = ip
        if proto == 17:
            udp = _udp(segment)
            if udp and udp[2]:
                sport, dport, payload = udp
                self.ip_flows[src].add((src, sport, dst, dport))
                self.ip_flows[dst].add((src, sport, dst, dport))
                self.udp.append((ts, src, sport, dst, dport, payload))
            return []
        if proto != 6:
            return []
        tcp = _tcp(segment)
        if tcp is None or not tcp[3]:
            return []
        sport, dport, seq, payload = tcp
        key = (src, sport, dst, dport)
        self.ip_flows[src].add(key)
        self.ip_flows[dst].add(key)
        flow = self.flows.get(key)
        if flow is None:
            flow = Flow()
            self.flows[key] = flow
        flow.push(seq, payload, ts)
        return []

    def _want(self, msg, proto):
        if proto != "zm":
            return True
        if self.keep is None:
            return True
        if isinstance(msg, list) and msg and isinstance(msg[0], str):
            return msg[0] in self.keep
        if isinstance(msg, str):
            return msg in self.keep
        return False

    def _count(self, msg):
        if isinstance(msg, list) and msg and isinstance(msg[0], str):
            self.by_msg[msg[0]] += 1
        elif isinstance(msg, str):
            self.by_msg[msg] += 1
        elif isinstance(msg, dict) and msg.get("_encrypted"):
            self.by_msg["<encrypted>"] += 1
        else:
            self.by_msg["<unparsed>"] += 1

    def _zm_rec(self, src, sport, dst, dport, stamp, body, ts, msg, enc=False):
        rec = {
            "ts": ts,
            "flow": self._flow_name(src, sport, dst, dport),
            "dir": self._dir(src, sport, dst, dport),
            "proto": "zm",
            "flags": struct.pack(">I", stamp).hex(),
            "stamp": stamp,
            "len": len(body),
            "msg": msg,
        }
        if enc:
            rec["enc"] = True
        return rec

    def _emit_plain(self, src, sport, dst, dport, stamp, body, ts, conn):
        msg = decode_payload(body)
        if isinstance(msg, list):
            self.keys.learn(msg, ts, conn)
        self.frames += 1
        if not self._want(msg, "zm"):
            return None
        self.kept += 1
        self._count(msg)
        return self._zm_rec(src, sport, dst, dport, stamp, body, ts, msg)

    def _emit_encrypted(self, item, msg):
        self.frames += 1
        self.decrypted += 1
        if not self._want(msg, "zm"):
            return None
        self.kept += 1
        self._count(msg)
        return self._zm_rec(
            item["src"],
            item["sport"],
            item["dst"],
            item["dport"],
            item["stamp"],
            item["body"],
            item["ts"],
            msg,
            enc=True,
        )

    def _emit_sealed(self, item):
        body = item["body"]
        msg = {"_encrypted": True, "len": len(body)}
        if len(body) <= 65536:
            msg["_body_hex"] = body.hex()
        self.frames += 1
        self.still_encrypted += 1
        if not self._want(msg, "zm"):
            return None
        self.kept += 1
        self._count(msg)
        return self._zm_rec(
            item["src"],
            item["sport"],
            item["dst"],
            item["dport"],
            item["stamp"],
            body,
            item["ts"],
            msg,
        )

    def _side_recs(self):
        recs = []
        for key, flow in self.flows.items():
            if flow.game or flow.nbytes == flow.reported:
                continue
            src, sport, dst, dport = key
            delta = flow.nbytes - flow.reported
            flow.reported = flow.nbytes
            hint = flow.hint or b""
            if flow.sni or _is_tls(hint):
                proto = "tls"
                detail = {"bytes": delta, "total": flow.nbytes}
                if flow.sni:
                    detail["sni"] = flow.sni
                msg = ["_tls", detail]
            elif flow.http:
                proto = "http"
                detail = dict(flow.http)
                detail["bytes"] = delta
                detail["total"] = flow.nbytes
                msg = ["_http", detail]
            else:
                proto = "tcp"
                msg = ["_tcp", {"bytes": delta, "total": flow.nbytes}]
            self.side_n += 1
            self.kept += 1
            self._count(msg)
            recs.append(
                {
                    "ts": flow.last_ts,
                    "flow": self._flow_name(src, sport, dst, dport),
                    "dir": self._dir(src, sport, dst, dport),
                    "proto": proto,
                    "flags": "",
                    "len": delta,
                    "msg": msg,
                }
            )
        return recs

    def _udp_recs(self):
        recs = []
        for ts, src, sport, dst, dport, payload in self.udp:
            text = None
            if payload and all(32 <= b < 127 or b in (9, 10, 13) for b in payload[:80]):
                text = payload[:80].decode("ascii", "replace")
            detail = {"bytes": len(payload), "hex": payload[:48].hex()}
            if text:
                detail["text"] = text
            msg = ["_udp", detail]
            self.side_n += 1
            self.kept += 1
            self._count(msg)
            recs.append(
                {
                    "ts": ts,
                    "flow": self._flow_name(src, sport, dst, dport),
                    "dir": self._dir(src, sport, dst, dport),
                    "proto": "udp",
                    "flags": "",
                    "len": len(payload),
                    "msg": msg,
                }
            )
        self.udp.clear()
        return recs

    def flush(self, final=False):
        fresh = []
        plain = []
        for key, flow in self.flows.items():
            src, sport, dst, dport = key
            conn = _conn(src, sport, dst, dport)
            for stamp, body, ts in flow.take_frames():
                if body.startswith(b"cr"):
                    fresh.append(
                        {
                            "ts": ts,
                            "src": src,
                            "sport": sport,
                            "dst": dst,
                            "dport": dport,
                            "conn": conn,
                            "stamp": stamp,
                            "body": body,
                        }
                    )
                else:
                    rec = self._emit_plain(src, sport, dst, dport, stamp, body, ts, conn)
                    if rec:
                        plain.append(rec)
            self.gaps += flow.gaps
            flow.gaps = 0
        pending = self.pending + fresh
        self.keys.try_lock(pending)
        decrypted = []
        still = []
        for item in pending:
            key = self.keys.key_at(item["ts"], item["conn"])
            msg = _decrypt_msg(key, item["body"]) if key else None
            if msg is None:
                still.append(item)
                continue
            rec = self._emit_encrypted(item, msg)
            if rec:
                decrypted.append(rec)
        recs = plain + decrypted + self._side_recs() + self._udp_recs()
        if final:
            self.pending = []
            for item in still:
                rec = self._emit_sealed(item)
                if rec:
                    recs.append(rec)
        else:
            if len(still) > 20000:
                for item in still[:-20000]:
                    rec = self._emit_sealed(item)
                    if rec:
                        recs.append(rec)
                still = still[-20000:]
            self.pending = still
        recs.sort(key=lambda rec: rec["ts"] or 0)
        return recs


class JsonlWriter:
    def __init__(self, path, flush_every=200):
        self.path = path
        self.flush_every = flush_every
        self.fp = open(path, "a", encoding="utf-8", buffering=1024 * 1024)
        self.n = 0
        self.t0 = None
        self.t1 = None

    def write_many(self, recs):
        if not recs:
            return
        write = self.fp.write
        dumps = json.dumps
        for rec in recs:
            write(dumps(rec, ensure_ascii=False, default=str) + "\n")
            self.n += 1
            ts = rec.get("ts")
            if ts:
                self.t0 = ts if self.t0 is None else min(self.t0, ts)
                self.t1 = ts if self.t1 is None else max(self.t1, ts)
            if self.n % self.flush_every == 0:
                self.fp.flush()

    def flush(self):
        self.fp.flush()

    def close(self):
        self.fp.flush()
        self.fp.close()


def parse_files(paths, out_path, profile="full", assembler=None):
    keep = PROFILES[profile]
    asm = assembler or Assembler(keep=keep)
    writer = JsonlWriter(out_path)
    try:
        for path in paths:
            for ts, raw, linktype in iter_pcap_file(path):
                asm.ingest(ts, raw, linktype)
            recs = asm.flush()
            if recs:
                writer.write_many(recs)
        recs = asm.flush(final=True)
        if recs:
            writer.write_many(recs)
    finally:
        writer.close()
    return asm, writer

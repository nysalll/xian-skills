"""Decrypt local Lua AssetBundle text assets.

The repeating XOR only transforms bundles the user already extracted from a
client they can access. It does not log in, bypass anti-cheat, or talk to a
game server.
"""

from __future__ import annotations

import io
import json
import re
from pathlib import Path

from xian_skills.errors import EnvError, XianError

KEY = b"m71"


def xor_m71(data: bytes) -> bytes:
    key = KEY
    return bytes(data[index] ^ key[index % 3] for index in range(len(data)))


def strip_unity_header(data: bytes) -> bytes:
    if len(data) > 19 and data[12:19] == b"UnityFS":
        return data[12:]
    index = data.find(b"UnityFS")
    if 0 <= index <= 64:
        return data[index:]
    return data


def sanitize(name: str) -> str:
    cleaned = "".join(ch if (ch.isprintable() and ch not in '<>:"|?*\\/') else "_" for ch in name)
    cleaned = cleaned.strip(" .") or "unknown"
    return cleaned[:180]


def _uleb(data: bytes, pos: int) -> tuple[int, int]:
    value = 0
    shift = 0
    while pos < len(data):
        byte = data[pos]
        pos += 1
        value |= (byte & 0x7F) << shift
        if byte < 0x80:
            return value, pos
        shift += 7
        if shift > 28:
            break
    return value, pos


def parse_lj_header(data: bytes) -> dict | None:
    if not data.startswith(b"\x1bLJ") or len(data) < 5:
        return None
    flags = data[4]
    info = {"magic": "LJ", "version": data[3], "flags": flags}
    # LuaJIT chunk name is a ULEB length followed by that many bytes, unless stripped.
    if not (flags & 0x02) and len(data) > 5:
        length, pos = _uleb(data, 5)
        if 0 < length < 240 and pos + length <= len(data):
            info["path"] = data[pos : pos + length].decode("utf-8", "ignore")
            return info
    at = data.find(b"@", 0, 80)
    if at >= 0:
        end = data.find(b"\x00", at)
        if end < 0:
            end = min(len(data), at + 80)
        info["path"] = data[at:end].decode("utf-8", "ignore")
    return info


def _output_name(info: dict | None, asset_name: str, bundle_stem: str, used: set[str]) -> tuple[str, str]:
    rel_dir = "unknown"
    if info and info.get("path"):
        parts = [part for part in info["path"].lstrip("@").replace("/", "\\").split("\\") if part]
        if len(parts) >= 2:
            rel_dir = sanitize(parts[0])
            fname = sanitize(parts[-1])
        else:
            fname = sanitize(parts[0] if parts else asset_name)
    else:
        fname = sanitize(asset_name if str(asset_name).endswith(".lua") else f"{asset_name}.lua")
    if not fname.endswith(".lua"):
        fname += ".lua"
    rel = f"{rel_dir}/{fname}"
    if rel in used:
        fname = sanitize(fname[:-4] + "__" + bundle_stem) + ".lua"
        rel = f"{rel_dir}/{fname}"
    used.add(rel)
    return rel_dir, fname


def extract_textassets(path: Path) -> list[tuple[str, bytes]]:
    try:
        import UnityPy
    except ImportError as exc:
        raise EnvError("缺少 UnityPy。在项目虚拟环境里执行 pip install UnityPy") from exc
    raw = strip_unity_header(path.read_bytes())
    try:
        env = UnityPy.load(io.BytesIO(raw))
    except Exception as exc:
        raise XianError(f"无法读取 AssetBundle {path.name}：{exc}", code=3) from exc
    found = []
    for obj in env.objects:
        if obj.type.name != "TextAsset":
            continue
        data = obj.read()
        script = data.m_Script
        if isinstance(script, str):
            script = script.encode("utf-8", "surrogateescape")
        found.append((getattr(data, "m_Name", None) or "unknown", bytes(script)))
    return found


def decode_raw(data: bytes) -> bytes:
    return xor_m71(data)


def decode_tree(src: Path, dest: Path, tag: str = "Lua64", limit: int | None = None) -> dict:
    src = Path(src)
    dest = Path(dest)
    if src.is_file():
        files = [src]
    elif src.is_dir():
        files = sorted(path for path in src.iterdir() if path.name.endswith(".unity3d"))
    else:
        raise XianError(f"输入不存在：{src}")
    if limit is not None:
        files = files[:limit]
    stats = {"bundles": 0, "assets": 0, "lj": 0, "fail": 0, "not_lj": 0}
    index = []
    used: set[str] = set()
    out_root = dest / tag
    for bundle in files:
        stats["bundles"] += 1
        try:
            assets = extract_textassets(bundle)
        except Exception:
            stats["fail"] += 1
            continue
        for name, raw in assets:
            stats["assets"] += 1
            decoded = xor_m71(raw)
            info = parse_lj_header(decoded)
            rel_dir, fname = _output_name(info, name, bundle.stem, used)
            out_path = out_root / rel_dir / fname
            out_path.parent.mkdir(parents=True, exist_ok=True)
            out_path.write_bytes(decoded)
            is_lj = decoded.startswith(b"\x1bLJ")
            stats["lj" if is_lj else "not_lj"] += 1
            index.append(
                {
                    "name": name,
                    "bundle": bundle.name,
                    "out": str(out_path),
                    "size": len(decoded),
                    "lj": is_lj,
                    "path": info.get("path") if info else None,
                }
            )
    dest.mkdir(parents=True, exist_ok=True)
    (dest / f"index_{tag}.json").write_text(
        json.dumps({"stats": stats, "files": index}, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    return stats


def fallback_strings(data: bytes) -> list[str]:
    found = []
    for match in re.finditer(rb"[\x20-\x7e]{4,}", data):
        found.append(match.group().decode("ascii", "ignore"))
    return found

"""Discover local adb executables and MuMu emulator endpoints."""

from __future__ import annotations

import json
import os
import re
from pathlib import Path

from xian_skills.config.model import normalize_path_str
from xian_skills.device.adb import Adb, adb_version, which_adb

_PORT_KEYS = ("adb_port", "adbport", "adb_host_port")
_MAX_FILES = 250


def _add_adb(found: list[str], path: Path | str | None) -> None:
    if not path:
        return
    cleaned = normalize_path_str(path)
    if not cleaned:
        return
    item = Path(cleaned)
    if item.is_file():
        norm = os.path.normcase(str(item.resolve()))
        if not any(os.path.normcase(str(Path(existing).resolve())) == norm for existing in found):
            found.append(str(item))


def _shallow_adb(root: Path, found: list[str], depth: int = 0) -> None:
    if depth > 4 or len(found) >= 10 or not root.is_dir():
        return
    try:
        children = list(root.iterdir())
    except OSError:
        return
    for child in children:
        if len(found) >= 10:
            return
        if child.is_file() and child.name.lower() == "adb.exe":
            _add_adb(found, child)
        elif child.is_dir():
            name = child.name.lower()
            if depth == 0 or any(token in name for token in ("mumu", "nemu", "netease", "nx_", "platform-tools", "shell", "adb")):
                _shallow_adb(child, found, depth + 1)


def _candidate_adbs(explicit: str = "") -> list[str]:
    found: list[str] = []
    if explicit:
        _add_adb(found, explicit)
        _add_adb(found, which_adb(explicit))
    local = os.environ.get("LOCALAPPDATA", "")
    appdata = os.environ.get("APPDATA", "")
    roots = [
        Path(r"C:\Program Files\Netease"),
        Path(r"C:\Program Files\NetEase"),
        Path(r"C:\Program Files\MuMu"),
        Path(r"D:\Program Files\Netease"),
        Path(r"D:\Program Files\NetEase"),
        Path(r"D:\Program Files\MuMu"),
    ]
    if local:
        roots.extend([Path(local) / "Netease", Path(local) / "NetEase"])
    if appdata:
        roots.extend([Path(appdata) / "Netease", Path(appdata) / "NetEase"])
    for root in roots:
        _shallow_adb(root, found)
    _add_adb(found, which_adb())
    direct = [
        Path.home() / ".xian-skills" / "tools" / "platform-tools" / "adb.exe",
        Path(local) / "Android" / "Sdk" / "platform-tools" / "adb.exe" if local else None,
        Path(r"C:\platform-tools\adb.exe"),
        Path(r"C:\Android\platform-tools\adb.exe"),
    ]
    for item in direct:
        _add_adb(found, item)
    return found


def inspect_adb_candidates(candidates: list[str]) -> dict:
    details = [adb_version(path) for path in candidates[:6]]
    releases = {row.get("release") for row in details if row.get("release")}
    protocols = {row.get("protocol") for row in details if row.get("protocol")}
    conflict = len(releases) > 1 or len(protocols) > 1
    warning = None
    if conflict:
        summary = ", ".join(f"{Path(row['path']).parent.name}/{Path(row['path']).name} ({row.get('release') or row.get('protocol')})" for row in details)
        warning = (
            f"检测到多套不同版本的 adb：{summary}。"
            "混用不同版本 adb 可能导致模拟器偶发 offline；建议始终使用同一套 adb（优先 MuMu 自带 shell\\adb.exe），"
            "或在配置中通过 xian init --adb <路径> 固定，无需强行停止其他程序正在使用的 ADB Server。"
        )
    return {"details": details, "version_conflict": conflict, "warning": warning}


def _walk_configs(root: Path, out: list[Path], depth: int = 0) -> None:
    if depth > 6 or len(out) >= _MAX_FILES or not root.is_dir():
        return
    try:
        children = list(root.iterdir())
    except OSError:
        return
    for child in children:
        if len(out) >= _MAX_FILES:
            return
        if child.is_file() and child.suffix.lower() in {".json", ".ini", ".cfg", ".txt"}:
            lowered = child.name.lower()
            if any(token in lowered for token in ("config", "vm_", "adb", "customer", "setting")):
                out.append(child)
        elif child.is_dir():
            lowered = child.name.lower()
            if depth == 0 or any(token in lowered for token in ("mumu", "nemu", "vms", "config", "netease")):
                _walk_configs(child, out, depth + 1)


def discover_endpoints() -> list[dict]:
    endpoints = []
    seen = set()
    roots = []
    local = os.environ.get("LOCALAPPDATA", "")
    appdata = os.environ.get("APPDATA", "")
    if appdata:
        roots.append(Path(appdata) / "Netease")
        roots.append(Path(appdata) / "NetEase")
    if local:
        roots.append(Path(local) / "Netease")
        roots.append(Path(local) / "NetEase")
    files: list[Path] = []
    for root in roots:
        _walk_configs(root, files)
    for path in files:
        try:
            text = path.read_text(encoding="utf-8", errors="replace")
        except OSError:
            continue
        if path.suffix.lower() == ".json":
            try:
                data = json.loads(text)
            except json.JSONDecodeError:
                data = None
            ports = sorted(_json_ports(data))
        else:
            ports = sorted(set(int(n) for n in re.findall(r"adb[_\-]?port\D{0,8}(\d{2,5})", text, re.I)))
        for port in ports:
            if not (1 <= port <= 65535):
                continue
            serial = f"127.0.0.1:{port}"
            if serial in seen:
                continue
            seen.add(serial)
            endpoints.append({"serial": serial, "source": str(path), "port": port})
    return endpoints


def _json_ports(node) -> set[int]:
    found: set[int] = set()
    if isinstance(node, dict):
        for key, value in node.items():
            lowered = str(key).lower()
            if lowered in _PORT_KEYS or lowered.endswith("adb_port"):
                if isinstance(value, int):
                    found.add(value)
                elif isinstance(value, str) and value.isdigit():
                    found.add(int(value))
            else:
                found.update(_json_ports(value))
    elif isinstance(node, list):
        for item in node:
            found.update(_json_ports(item))
    return found


def choose_adb(explicit: str = "") -> tuple[str | None, list[str]]:
    candidates = _candidate_adbs(explicit)
    return (candidates[0] if candidates else None), candidates


def list_devices(exe: str, auto_connect: bool = True, endpoints: list[dict] | None = None) -> dict:
    adb = Adb(exe)
    before = adb.devices()
    connected = []
    if auto_connect:
        online = {row["serial"] for row in before if row.get("state") == "device"}
        offline = {row["serial"] for row in before if row.get("state") == "offline"}
        for serial in sorted(offline):
            rec = adb.reconnect(serial)
            connected.append({"serial": serial, "action": "reconnect_offline", "message": rec.get("connect", "")})
        for item in endpoints or []:
            serial = item["serial"]
            if serial in online or serial in offline:
                continue
            message = adb.connect(serial)
            connected.append({"serial": serial, "action": "connect", "message": message, "source": item.get("source")})
    devices = adb.devices()
    if auto_connect:
        still_offline = [row["serial"] for row in devices if row.get("state") == "offline"]
        if still_offline:
            for serial in still_offline:
                rec = adb.reconnect(serial)
                connected.append({"serial": serial, "action": "retry_offline", "message": rec.get("connect", "")})
            devices = adb.devices()
    return {
        "adb": exe,
        "devices": devices,
        "online": [row["serial"] for row in devices if row.get("state") == "device"],
        "offline": [row["serial"] for row in devices if row.get("state") == "offline"],
        "connect_attempts": connected,
        "endpoints": endpoints or [],
    }

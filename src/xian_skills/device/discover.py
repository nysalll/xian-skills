"""Discover local adb executables and MuMu emulator endpoints."""

from __future__ import annotations

import json
import os
import re
from pathlib import Path

from xian_skills.device.adb import Adb, which_adb

_PORT_KEYS = ("adb_port", "adbport", "adb_host_port")
_MAX_FILES = 250


def _add_adb(found: list[str], path: Path | str | None) -> None:
    if not path:
        return
    item = Path(path)
    if item.is_file():
        text = str(item)
        if text not in found:
            found.append(text)


def _shallow_adb(root: Path, found: list[str], depth: int = 0) -> None:
    if depth > 4 or len(found) >= 8 or not root.is_dir():
        return
    try:
        children = list(root.iterdir())
    except OSError:
        return
    for child in children:
        if len(found) >= 8:
            return
        if child.is_file() and child.name.lower() == "adb.exe":
            _add_adb(found, child)
        elif child.is_dir():
            name = child.name.lower()
            if depth == 0 or any(token in name for token in ("mumu", "nemu", "netease", "platform-tools", "shell", "adb")):
                _shallow_adb(child, found, depth + 1)


def _candidate_adbs(explicit: str = "") -> list[str]:
    found: list[str] = []
    _add_adb(found, explicit)
    _add_adb(found, which_adb(explicit) if explicit else which_adb())
    local = os.environ.get("LOCALAPPDATA", "")
    appdata = os.environ.get("APPDATA", "")
    direct = [
        Path(local) / "Android" / "Sdk" / "platform-tools" / "adb.exe" if local else None,
        Path.home() / ".xian-skills" / "tools" / "platform-tools" / "adb.exe",
        Path(r"C:\platform-tools\adb.exe"),
        Path(r"C:\Android\platform-tools\adb.exe"),
    ]
    for item in direct:
        _add_adb(found, item)
    roots = []
    if local:
        roots.extend([Path(local) / "Netease", Path(local) / "NetEase"])
    if appdata:
        roots.extend([Path(appdata) / "Netease", Path(appdata) / "NetEase"])
    roots.extend(
        [
            Path(r"C:\Program Files\Netease"),
            Path(r"C:\Program Files\NetEase"),
            Path(r"C:\Program Files\MuMu"),
        ]
    )
    for root in roots:
        _shallow_adb(root, found)
    return found


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
        known = {row["serial"] for row in before}
        for item in endpoints or []:
            serial = item["serial"]
            if serial in known:
                continue
            message = adb.connect(serial)
            connected.append({"serial": serial, "message": message, "source": item.get("source")})
    devices = adb.devices()
    return {"adb": exe, "devices": devices, "connect_attempts": connected, "endpoints": endpoints or []}

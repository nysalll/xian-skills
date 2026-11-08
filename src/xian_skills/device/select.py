"""Pick one adb.exe and keep using it. A second adb server is what flips MuMu offline."""

from __future__ import annotations

import os
import subprocess
from pathlib import Path

from xian_skills.device.adb import Adb
from xian_skills.device.discover import _candidate_adbs, discover_endpoints


def adb_source(path: str) -> str:
    text = str(path).lower().replace("/", "\\")
    if any(token in text for token in ("mumu", "nemu", "netease")):
        return "mumu"
    if "platform-tools" in text or "\\android\\sdk\\" in text:
        return "android-sdk"
    return "other"


def running_adb_exes() -> list[str]:
    if os.name != "nt":
        return []
    command = (
        "Get-CimInstance Win32_Process -Filter \"Name = 'adb.exe'\" | "
        "ForEach-Object { $_.ExecutablePath }"
    )
    try:
        result = subprocess.run(
            ["powershell", "-NoProfile", "-Command", command],
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=20,
        )
    except (OSError, subprocess.TimeoutExpired):
        return []
    found = []
    for line in (result.stdout or "").splitlines():
        path = line.strip()
        if path and Path(path).is_file() and path not in found:
            found.append(path)
    return found


def _same(left: str, right: str) -> bool:
    try:
        return Path(left).resolve() == Path(right).resolve()
    except OSError:
        return Path(left) == Path(right)


def select_adb(explicit: str = "", auto_connect: bool = True, replace: bool = False) -> dict:
    """Choose one adb binary. Never start a second server while one is already running."""
    candidates = [{"path": path, "source": adb_source(path)} for path in _candidate_adbs(explicit)]
    running = running_adb_exes()
    requested = explicit if explicit and Path(explicit).is_file() else ""
    note = ""
    if requested and running and not any(_same(requested, item) for item in running) and not replace:
        chosen = running[0]
        note = "已有 adb 在运行，本次继续用它，避免把 MuMu 打成 offline。要换 ADB 时先确认，再加 --replace-adb --yes。"
    elif requested:
        chosen = requested
    elif running:
        chosen = running[0]
        note = "复用已经启动的 adb，不另开一套服务。"
    else:
        mumu = [item["path"] for item in candidates if item["source"] == "mumu"]
        chosen = mumu[0] if mumu else (candidates[0]["path"] if candidates else "")
        note = "当前没有 adb 服务。优先使用 MuMu 自带的 adb。" if mumu else ""
    if not chosen:
        return {
            "adb": None,
            "source": "",
            "candidates": candidates,
            "running": running,
            "devices": [],
            "online": [],
            "offline": [],
            "note": "未找到 adb",
            "diagnosis": "",
            "connect_attempts": [],
        }
    endpoints = discover_endpoints() if auto_connect else []
    before = Adb(chosen).devices()
    known = {row["serial"] for row in before}
    attempts = []
    if auto_connect:
        tool = Adb(chosen)
        for item in endpoints:
            serial = item["serial"]
            if serial in known:
                continue
            attempts.append({"serial": serial, "message": tool.connect(serial), "source": item.get("source")})
    devices = Adb(chosen).devices()
    online = [row["serial"] for row in devices if row.get("state") == "device"]
    offline = [row["serial"] for row in devices if row.get("state") == "offline"]
    diagnosis = ""
    if offline:
        diagnosis = (
            "这些设备是 offline。不要再换一个 adb.exe。"
            "两套 ADB 抢同一个服务时就会这样。请关掉多余的 adb.exe，只用上面选中的这一条。"
        )
    return {
        "adb": chosen,
        "source": adb_source(chosen),
        "candidates": candidates,
        "running": running,
        "devices": devices,
        "online": online,
        "offline": offline,
        "note": note,
        "diagnosis": diagnosis,
        "connect_attempts": attempts,
    }

"""Environment checks. Presence of a file is not a passed feature test."""

from __future__ import annotations

import importlib.util
import os
import shutil
import sys
from pathlib import Path

from xian_skills.device.discover import choose_adb, discover_endpoints, list_devices
from xian_skills.version import __version__


def _spec(name: str) -> bool:
    try:
        return importlib.util.find_spec(name) is not None
    except (ImportError, ValueError):
        return False


def check_python() -> dict:
    return {
        "name": "python",
        "ok": sys.version_info >= (3, 10),
        "detail": sys.version.split()[0],
        "prefix": sys.prefix,
        "venv": sys.prefix != getattr(sys, "base_prefix", sys.prefix),
        "fix": "从 https://www.python.org/downloads/windows/ 安装 Python 3.10 或更新版本，并勾选 Add python.exe to PATH。",
    }


def check_modules() -> list[dict]:
    modules = [
        ("msgpack", "decode", "pip install msgpack"),
        ("Crypto", "decode", "pip install pycryptodome"),
        ("UnityPy", "lua", "pip install UnityPy"),
        ("frida", "runtime", "pip install frida"),
    ]
    rows = []
    for name, extra, fix in modules:
        ok = _spec(name)
        rows.append(
            {
                "name": name,
                "ok": ok,
                "extra": extra,
                "detail": "已安装" if ok else "未安装",
                "fix": None if ok else fix,
            }
        )
    return rows


def check_tools(cfg) -> list[dict]:
    rows = []
    for key, label, purpose in (
        ("decompiler_path", "luajit-decompiler", "LuaJIT 反编译"),
        ("vgmstream_path", "vgmstream", "CRI 音频解码"),
        ("ffmpeg_path", "ffmpeg", "视频转码"),
    ):
        raw = (cfg.data.get(key) or "").strip()
        path = Path(raw) if raw else None
        which = shutil.which(label) if label != "luajit-decompiler" else None
        ok = bool(path and path.is_file()) or bool(which)
        rows.append(
            {
                "name": label,
                "ok": ok,
                "detail": str(path or which or "未配置"),
                "purpose": purpose,
                "fix": f"把可执行文件路径写入配置 {key}。仓库不附带这些程序。",
            }
        )
    return rows


def doctor(cfg, probe_devices: bool = True) -> dict:
    py = check_python()
    modules = check_modules()
    tools = check_tools(cfg)
    adb_path, adb_candidates = choose_adb(cfg.data.get("adb_path") or "")
    device_report = None
    if probe_devices and adb_path:
        try:
            endpoints = discover_endpoints() if cfg.data.get("auto_connect", True) else []
            device_report = list_devices(adb_path, auto_connect=bool(cfg.data.get("auto_connect", True)), endpoints=endpoints)
        except Exception as exc:
            device_report = {"adb": adb_path, "error": f"{type(exc).__name__}: {exc}", "devices": []}
    elif not adb_path:
        device_report = {"adb": None, "devices": [], "error": "未找到 adb"}
    ready = [row["serial"] for row in (device_report or {}).get("devices") or [] if row.get("state") == "device"]
    return {
        "tool_version": __version__,
        "home": str(Path(os.environ.get("XIAN_HOME") or (Path.home() / ".xian-skills"))),
        "data_dir": str(cfg.data_dir),
        "python": py,
        "modules": modules,
        "external_tools": tools,
        "adb": {
            "selected": adb_path,
            "candidates": adb_candidates,
            "ok": bool(adb_path),
            "fix": "安装 Android SDK Platform-Tools，或在配置里设置 adb_path。官方压缩包：https://dl.google.com/android/repository/platform-tools-latest-windows.zip",
        },
        "devices": device_report,
        "online_devices": ready,
    }


def format_doctor(report: dict) -> str:
    py = report["python"]
    lines = [
        f"xian-skills {report['tool_version']}",
        f"Python {py['detail']}  venv={py['venv']}  {'可用' if py['ok'] else '版本过低'}",
        f"数据目录 {report['data_dir']}",
        f"adb {report['adb']['selected'] or '未找到'}",
    ]
    devices = (report.get("devices") or {}).get("devices") or []
    if devices:
        lines.append("设备：")
        for row in devices:
            lines.append(f"  {row['serial']}  {row['state']}  {row.get('model') or ''}")
    else:
        lines.append("设备：没有已连接设备")
    missing = [row for row in report["modules"] if not row["ok"]]
    if missing:
        lines.append("缺少 Python 包：" + ", ".join(row["name"] for row in missing))
    else:
        lines.append("可选 Python 包都已安装")
    return "\n".join(lines)

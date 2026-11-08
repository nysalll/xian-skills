"""Environment checks. Presence of a file is not a passed feature test."""

from __future__ import annotations

import importlib.util
import os
import shutil
import sys
from pathlib import Path

from xian_skills.device.discover import choose_adb
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
    from xian_skills.tools.decompiler import resolve_decompiler

    rows = []
    for key, label, purpose in (
        ("decompiler_path", "luajit-decompiler", "LuaJIT 反编译"),
        ("vgmstream_path", "vgmstream", "CRI 音频解码"),
        ("ffmpeg_path", "ffmpeg", "视频转码"),
    ):
        if key == "decompiler_path":
            path = resolve_decompiler(cfg.data.get(key) or "")
            which = None
        else:
            raw = cfg.tool_path(key, which_names=(label, f"{label}-cli") if label == "vgmstream" else (label,))
            path = Path(raw) if raw else None
            which = shutil.which(label)
        ok = bool(path and path.is_file()) or bool(which)
        rows.append(
            {
                "name": label,
                "ok": ok,
                "detail": str(path if (path and path.is_file()) else (which or "未配置")),
                "purpose": purpose,
                "fix": (
                    "确认后执行 xian tools decompiler --install --yes，或把可执行文件路径写入配置 decompiler_path。"
                    if key == "decompiler_path"
                    else f"把可执行文件路径写入配置 {key}。仓库不附带这些程序。"
                ),
            }
        )
    return rows


def doctor(cfg, probe_devices: bool = True) -> dict:
    py = check_python()
    modules = check_modules()
    tools = check_tools(cfg)
    from xian_skills.device.select import adb_source, select_adb
    from xian_skills.tools.decompiler import status as decompiler_status

    device_report = None
    if probe_devices:
        try:
            device_report = select_adb(cfg.data.get("adb_path") or "", auto_connect=bool(cfg.data.get("auto_connect", True)))
        except Exception as exc:
            device_report = {"adb": None, "error": f"{type(exc).__name__}: {exc}", "devices": [], "online": [], "offline": []}
    else:
        from xian_skills.device.discover import choose_adb

        adb_path, adb_candidates = choose_adb(cfg.data.get("adb_path") or "")
        device_report = {
            "adb": adb_path,
            "source": adb_source(adb_path) if adb_path else "",
            "candidates": [{"path": item, "source": adb_source(item)} for item in adb_candidates],
            "devices": [],
            "online": [],
            "offline": [],
            "note": "",
            "diagnosis": "",
        }
    adb_path = (device_report or {}).get("adb")
    ready = list((device_report or {}).get("online") or [])
    decompiler = decompiler_status(cfg.data.get("decompiler_path") or "")
    return {
        "tool_version": __version__,
        "home": str(Path(os.environ.get("XIAN_HOME") or (Path.home() / ".xian-skills"))),
        "data_dir": str(cfg.data_dir),
        "python": py,
        "modules": modules,
        "external_tools": tools,
        "adb": {
            "selected": adb_path,
            "source": (device_report or {}).get("source"),
            "candidates": (device_report or {}).get("candidates") or [],
            "running": (device_report or {}).get("running") or [],
            "offline": (device_report or {}).get("offline") or [],
            "note": (device_report or {}).get("note") or "",
            "diagnosis": (device_report or {}).get("diagnosis") or "",
            "ok": bool(adb_path),
            "fix": "安装 Android SDK Platform-Tools，或在配置里设置 adb_path。已有 adb 服务时不要再换一个 adb.exe。",
        },
        "decompiler": decompiler,
        "devices": device_report,
        "online_devices": ready,
    }


def format_doctor(report: dict) -> str:
    py = report["python"]
    lines = [
        f"xian-skills {report['tool_version']}",
        f"Python {py['detail']}  venv={py['venv']}  {'可用' if py['ok'] else '版本过低'}",
        f"数据目录 {report['data_dir']}",
        f"adb {report['adb']['selected'] or '未找到'}  来源 {report['adb'].get('source') or '未知'}",
    ]
    if report["adb"].get("note"):
        lines.append(report["adb"]["note"])
    if report["adb"].get("diagnosis"):
        lines.append(report["adb"]["diagnosis"])
    devices = (report.get("devices") or {}).get("devices") or []
    if devices:
        lines.append("设备：")
        for row in devices:
            lines.append(f"  {row['serial']}  {row['state']}  {row.get('model') or ''}")
    else:
        lines.append("设备：没有已连接设备")
    decompiler = report.get("decompiler") or {}
    if decompiler.get("verified_hash"):
        lines.append("反编译器：已核对官方 SHA256")
    elif (decompiler.get("configured") or {}).get("present"):
        lines.append("反编译器：路径存在，但不是已固定的官方文件")
    else:
        lines.append("反编译器：未安装。确认后执行 xian tools decompiler --install --yes")
    missing = [row for row in report["modules"] if not row["ok"]]
    if missing:
        lines.append("缺少 Python 包：" + ", ".join(row["name"] for row in missing))
    else:
        lines.append("可选 Python 包都已安装")
    return "\n".join(lines)

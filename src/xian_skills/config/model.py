"""User configuration. Tool settings live outside the data warehouse."""

from __future__ import annotations

import json
import os
import re
import shutil
import sys
from dataclasses import dataclass, field
from pathlib import Path

from xian_skills.version import SCHEMA_VERSION, __version__

_MSYS_DRIVE_RE = re.compile(r"^/([a-zA-Z])/(.*)$")
_PS_ENV_RE = re.compile(r"\$env:([A-Za-z_][A-Za-z0-9_]*)", re.I)
_POSIX_ENV_RE = re.compile(r"\$\{?([A-Za-z_][A-Za-z0-9_]*)\}?")
_BAD_JSON_ESCAPE_RE = re.compile(r'\\(?![/\"\\bfnrt]|u[0-9a-fA-F]{4})')
_UNICODE_DRIVE_ESCAPE_RE = re.compile(r'([A-Za-z]:)\\u(?![0-9a-fA-F]{4})')


def normalize_path_str(raw: str | Path | None) -> str:
    if raw is None:
        return ""
    text = str(raw).strip()
    if not text:
        return ""
    while len(text) >= 2 and text[0] == text[-1] and text[0] in {'"', "'"}:
        text = text[1:-1].strip()
    # Handle Windows CommandLineToArgvW trailing quote artifact from `\"` at end of path
    if text.endswith(('"', "'")) and not text.startswith(('"', "'")):
        text = text[:-1].strip()
    text = _PS_ENV_RE.sub(lambda m: os.environ.get(m.group(1), m.group(0)), text)
    if "$HOME" in text or "${HOME}" in text:
        home_str = str(Path.home())
        text = text.replace("${HOME}", home_str).replace("$HOME", home_str)
    text = os.path.expandvars(text)
    if text.startswith("~"):
        text = os.path.expanduser(text)
    if os.name == "nt":
        msys = _MSYS_DRIVE_RE.match(text)
        if msys:
            text = f"{msys.group(1).upper()}:/{msys.group(2)}"
    return str(Path(text)) if text else ""


def normalize_path(raw: str | Path | None) -> Path | None:
    cleaned = normalize_path_str(raw)
    return Path(cleaned) if cleaned else None


def home_dir() -> Path:
    override = os.environ.get("XIAN_HOME")
    if override:
        return normalize_path(override) or (Path.home() / ".xian-skills")
    return Path.home() / ".xian-skills"


def config_path() -> Path:
    override = os.environ.get("XIAN_CONFIG")
    if override:
        return normalize_path(override) or (home_dir() / "config.json")
    return home_dir() / "config.json"


def default_channels() -> dict:
    return {
        "official": {"label": "正式服", "package": "com.leiting.xian"},
        "zhengdao": {"label": "证道服", "package": "com.leiting.m71"},
    }


def default_document() -> dict:
    return {
        "schema": SCHEMA_VERSION,
        "tool_version": __version__,
        "data_dir": str(home_dir() / "data"),
        "adb_path": "",
        "device": "",
        "decompiler_path": "",
        "vgmstream_path": "",
        "ffmpeg_path": "",
        "auto_connect": True,
        "channels": default_channels(),
    }


@dataclass
class Config:
    path: Path
    data: dict = field(default_factory=default_document)

    @property
    def data_dir(self) -> Path:
        override = os.environ.get("XIAN_DATA")
        if override:
            return normalize_path(override) or (home_dir() / "data")
        return normalize_path(self.data.get("data_dir")) or (home_dir() / "data")

    def tool_path(self, key: str, filenames: tuple[str, ...] = (), which_names: tuple[str, ...] = ()) -> str:
        raw = normalize_path_str(self.data.get(key) or "")
        if raw and Path(raw).is_file():
            return str(Path(raw))
        tools_root = home_dir() / "tools"
        if tools_root.is_dir():
            for fname in filenames:
                direct = tools_root / fname
                if direct.is_file():
                    return str(direct)
                for child in sorted(tools_root.iterdir()):
                    if child.is_dir() and (child / fname).is_file():
                        return str(child / fname)
        for name in which_names:
            found = shutil.which(name)
            if found:
                return found
        return raw

    def channel(self, name: str) -> dict:
        channels = self.data.get("channels") or {}
        if name not in channels:
            known = ", ".join(sorted(channels)) or "(none)"
            raise KeyError(f"未知渠道 {name}。已配置：{known}")
        return channels[name]

    def package(self, name: str) -> str:
        return self.channel(name)["package"]


def _loads_tolerant(text: str) -> dict:
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        repaired = _UNICODE_DRIVE_ESCAPE_RE.sub(r"\1\\\\u", text)
        repaired = _BAD_JSON_ESCAPE_RE.sub(r"\\\\", repaired)
        return json.loads(repaired)


def load_config(path: Path | None = None) -> Config:
    path = normalize_path(path) if path else config_path()
    base = default_document()
    if path.is_file():
        loaded = _loads_tolerant(path.read_text(encoding="utf-8-sig"))
        if not isinstance(loaded, dict):
            raise ValueError(f"配置不是对象：{path}")
        schema = int(loaded.get("schema") or 1)
        if schema > SCHEMA_VERSION:
            raise ValueError(
                f"配置 schema={schema} 高于当前工具 schema={SCHEMA_VERSION}，请升级 xian-skills"
            )
        for path_key in ("data_dir", "adb_path", "decompiler_path", "vgmstream_path", "ffmpeg_path"):
            if loaded.get(path_key):
                loaded[path_key] = normalize_path_str(loaded[path_key])
        channels = default_channels()
        channels.update(loaded.get("channels") or {})
        base.update(loaded)
        base["channels"] = channels
        base["schema"] = SCHEMA_VERSION
    return Config(path=path, data=base)


def write_cli_wrappers(base_home: Path | None = None) -> dict:
    root = Path(base_home) if base_home else home_dir()
    bin_dir = root / "bin"
    bin_dir.mkdir(parents=True, exist_ok=True)
    py_exe = str(Path(sys.executable).resolve())
    py_posix = Path(sys.executable).resolve().as_posix()

    cmd_path = bin_dir / "xian.cmd"
    cmd_path.write_text(
        f'@echo off\r\n"{py_exe}" -m xian_skills %*\r\n',
        encoding="utf-8",
    )

    ps1_path = bin_dir / "xian.ps1"
    ps1_path.write_text(
        f'& "{py_exe}" -m xian_skills @args\r\nexit $LASTEXITCODE\r\n',
        encoding="utf-8",
    )

    sh_path = bin_dir / "xian"
    sh_path.write_text(
        f'#!/usr/bin/env sh\nexec "{py_posix}" -m xian_skills "$@"\n',
        encoding="utf-8",
    )
    return {"bin_dir": str(bin_dir), "cmd": str(cmd_path), "ps1": str(ps1_path), "sh": str(sh_path)}


def save_config(cfg: Config) -> None:
    cfg.path.parent.mkdir(parents=True, exist_ok=True)
    for path_key in ("data_dir", "adb_path", "decompiler_path", "vgmstream_path", "ffmpeg_path"):
        if cfg.data.get(path_key):
            cfg.data[path_key] = normalize_path_str(cfg.data[path_key])
    cfg.data["schema"] = SCHEMA_VERSION
    cfg.data["tool_version"] = __version__
    text = json.dumps(cfg.data, ensure_ascii=False, indent=2) + "\n"
    tmp = cfg.path.with_suffix(cfg.path.suffix + ".tmp")
    tmp.write_text(text, encoding="utf-8")
    os.replace(tmp, cfg.path)

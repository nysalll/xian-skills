"""User configuration. Tool settings live outside the data warehouse."""

from __future__ import annotations

import json
import os
from dataclasses import dataclass, field
from pathlib import Path

from xian_skills.version import SCHEMA_VERSION, __version__


def home_dir() -> Path:
    override = os.environ.get("XIAN_HOME")
    if override:
        return Path(override)
    return Path.home() / ".xian-skills"


def config_path() -> Path:
    override = os.environ.get("XIAN_CONFIG")
    if override:
        return Path(override)
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
            return Path(override)
        return Path(self.data.get("data_dir") or (home_dir() / "data"))

    def channel(self, name: str) -> dict:
        channels = self.data.get("channels") or {}
        if name not in channels:
            known = ", ".join(sorted(channels)) or "(none)"
            raise KeyError(f"未知渠道 {name}。已配置：{known}")
        return channels[name]

    def package(self, name: str) -> str:
        return self.channel(name)["package"]


def load_config(path: Path | None = None) -> Config:
    path = Path(path) if path else config_path()
    base = default_document()
    if path.is_file():
        loaded = json.loads(path.read_text(encoding="utf-8"))
        if not isinstance(loaded, dict):
            raise ValueError(f"配置不是对象：{path}")
        schema = int(loaded.get("schema") or 1)
        if schema > SCHEMA_VERSION:
            raise ValueError(
                f"配置 schema={schema} 高于当前工具 schema={SCHEMA_VERSION}，请升级 xian-skills"
            )
        channels = default_channels()
        channels.update(loaded.get("channels") or {})
        base.update(loaded)
        base["channels"] = channels
        base["schema"] = SCHEMA_VERSION
    return Config(path=path, data=base)


def save_config(cfg: Config) -> None:
    cfg.path.parent.mkdir(parents=True, exist_ok=True)
    cfg.data["schema"] = SCHEMA_VERSION
    cfg.data["tool_version"] = __version__
    text = json.dumps(cfg.data, ensure_ascii=False, indent=2) + "\n"
    tmp = cfg.path.with_suffix(cfg.path.suffix + ".tmp")
    tmp.write_text(text, encoding="utf-8")
    os.replace(tmp, cfg.path)

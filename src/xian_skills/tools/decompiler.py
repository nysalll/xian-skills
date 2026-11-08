"""Pinned LuaJIT decompiler release. Nothing is downloaded unless the user passes --yes."""

from __future__ import annotations

import hashlib
import urllib.request
from pathlib import Path

from xian_skills.config.model import Config, save_config
from xian_skills.errors import EnvError, NeedConfirm, XianError

RELEASE = {
    "repo": "marsinator358/luajit-decompiler-v2",
    "tag": "Mar_24_2024",
    "asset": "luajit-decompiler-v2.exe",
    "url": "https://github.com/marsinator358/luajit-decompiler-v2/releases/download/Mar_24_2024/luajit-decompiler-v2.exe",
    "sha256": "d98fedf8041df653904db28a1daaf65ce355487307ae49c573ae94491140bb6a",
    "size": 287232,
    "license": "MIT",
    "copyright": "Copyright (C) 2023 marsinator358. LuaJIT Copyright (C) 2005-2023 Mike Pall. Lua Copyright (C) 1994-2023 Lua.org, PUC-Rio.",
    "note": "Release tag is Mar_24_2024. The Windows exe asset was rebuilt on 2026-05-14 and published on that same release.",
}

_LICENSE_TEXT = """MIT License

LuaJIT Decompiler v2
Copyright (C) 2023 marsinator358

LuaJIT
Copyright (C) 2005-2023 Mike Pall. All rights reserved.

Lua
Copyright (C) 1994-2023 Lua.org, PUC-Rio.

Permission is hereby granted, free of charge, to any person obtaining a copy
of this software and associated documentation files (the "Software"), to deal
in the Software without restriction, including without limitation the rights
to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
copies of the Software, and to permit persons to whom the Software is
furnished to do so, subject to the following conditions:

The above copyright notice and this permission notice shall be included in all
copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
SOFTWARE.
"""


def install_dir(home: Path | None = None) -> Path:
    root = Path(home) if home else Path.home() / ".xian-skills"
    return root / "tools" / "luajit-decompiler-v2" / RELEASE["tag"]


def target_exe(home: Path | None = None) -> Path:
    return install_dir(home) / RELEASE["asset"]


def file_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with Path(path).open("rb") as handle:
        for chunk in iter(lambda: handle.read(1 << 20), b""):
            digest.update(chunk)
    return digest.hexdigest()


def inspect_exe(path: Path) -> dict:
    path = Path(path)
    if not path.is_file():
        return {"present": False, "path": str(path), "sha256_ok": False}
    digest = file_sha256(path)
    size = path.stat().st_size
    return {
        "present": True,
        "path": str(path),
        "size": size,
        "sha256": digest,
        "sha256_ok": digest == RELEASE["sha256"] and size == RELEASE["size"],
    }


def status(configured: str = "", home: Path | None = None) -> dict:
    pinned = target_exe(home)
    pinned_info = inspect_exe(pinned)
    configured_info = inspect_exe(Path(configured)) if configured else {"present": False, "sha256_ok": False}
    usable = configured_info.get("present") or pinned_info.get("sha256_ok")
    return {
        "release": RELEASE,
        "configured_path": configured,
        "configured": configured_info,
        "pinned_copy": pinned_info,
        "usable": bool(usable),
        "verified_hash": bool(configured_info.get("sha256_ok") or pinned_info.get("sha256_ok")),
    }


def install(cfg: Config, yes: bool = False, home: Path | None = None) -> dict:
    if not yes:
        raise NeedConfirm(
            "将从 GitHub Release 下载 LuaJIT Decompiler v2（MIT，marsinator358 / Mike Pall / Lua.org）。"
            f"地址 {RELEASE['url']}，SHA256 {RELEASE['sha256']}。"
            "文件只保存到用户目录的 tools 里，并写入 decompiler_path。不会修改游戏或模拟器。"
            "确认后执行 xian tools decompiler --install --yes。",
            payload={"release": RELEASE},
        )
    dest = target_exe(home)
    dest.parent.mkdir(parents=True, exist_ok=True)
    partial = dest.with_suffix(".partial")
    try:
        with urllib.request.urlopen(RELEASE["url"], timeout=60) as response, partial.open("wb") as handle:
            while True:
                chunk = response.read(1 << 20)
                if not chunk:
                    break
                handle.write(chunk)
    except Exception as exc:
        partial.unlink(missing_ok=True)
        raise EnvError(
            f"下载失败：{exc}。可以稍后重试，或自己从 {RELEASE['url']} 下载，核对 SHA256 后再把路径写入 decompiler_path。"
        ) from exc
    info = inspect_exe(partial)
    if not info["sha256_ok"]:
        partial.unlink(missing_ok=True)
        raise XianError(
            f"下载内容的 SHA256 是 {info.get('sha256')}，与固定值不符。已删除该文件，没有执行它。",
            code=3,
            payload=info,
        )
    partial.replace(dest)
    (dest.parent / "LICENSE").write_text(_LICENSE_TEXT, encoding="utf-8")
    cfg.data["decompiler_path"] = str(dest)
    save_config(cfg)
    return {"installed": str(dest), "sha256_ok": True, "tag": RELEASE["tag"]}

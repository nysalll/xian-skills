"""ADB process wrapper for device discovery, shell commands, and file pulls."""

from __future__ import annotations

import re
import shutil
import subprocess
from pathlib import Path

from xian_skills.config.model import normalize_path_str
from xian_skills.errors import EnvError, XianError

_ADB_VER_RE = re.compile(r"Android Debug Bridge version\s+([\d.]+)", re.I)
_ADB_REL_RE = re.compile(r"Version\s+([\d.]+(?:-[\w.]+)?)", re.I)


def which_adb(explicit: str = "") -> str | None:
    cleaned = normalize_path_str(explicit)
    if cleaned:
        path = Path(cleaned)
        if path.is_file():
            return str(path)
        found = shutil.which(cleaned)
        return found
    return shutil.which("adb")


def adb_version(exe: str) -> dict:
    if not exe:
        return {"path": "", "protocol": None, "release": None}
    try:
        proc = subprocess.run(
            [exe, "version"],
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=10,
        )
    except Exception as exc:
        return {"path": exe, "protocol": None, "release": None, "error": str(exc)}
    text = ((proc.stdout or "") + "\n" + (proc.stderr or "")).strip()
    ver_m = _ADB_VER_RE.search(text)
    rel_m = _ADB_REL_RE.search(text)
    lowered = exe.lower()
    kind = "mumu" if any(k in lowered for k in ("mumu", "nemu", "netease", "nx_")) else "sdk_or_system"
    return {
        "path": exe,
        "protocol": ver_m.group(1) if ver_m else None,
        "release": rel_m.group(1) if rel_m else None,
        "kind": kind,
    }


class Adb:
    def __init__(self, exe: str, serial: str = ""):
        if not exe:
            raise EnvError("没有可用的 adb")
        self.exe = exe
        self.serial = serial

    def run(self, args: list[str], timeout: int = 60) -> subprocess.CompletedProcess:
        try:
            return subprocess.run(
                [self.exe, *args],
                capture_output=True,
                text=True,
                encoding="utf-8",
                errors="replace",
                timeout=timeout,
            )
        except FileNotFoundError as exc:
            raise EnvError(f"无法执行 adb：{self.exe}") from exc
        except subprocess.TimeoutExpired as exc:
            raise XianError(f"adb 超时：{' '.join(args[:4])}", code=3) from exc

    def _is_offline_output(self, result: subprocess.CompletedProcess) -> bool:
        if result.returncode == 0:
            return False
        detail = ((result.stderr or "") + "\n" + (result.stdout or "")).lower()
        return "device offline" in detail or ("offline" in detail and "error:" in detail)

    def reconnect(self, serial: str = "") -> dict:
        target = serial or self.serial
        if not target:
            return {"serial": "", "reconnected": False}
        if target.startswith(("127.0.0.1:", "localhost:")):
            disc = self.run(["disconnect", target], timeout=15)
            conn = self.run(["connect", target], timeout=20)
            msg = ((conn.stdout or "") + (conn.stderr or "")).strip()
            return {
                "serial": target,
                "reconnected": "connected" in msg.lower(),
                "disconnect": ((disc.stdout or "") + (disc.stderr or "")).strip(),
                "connect": msg,
            }
        rec = self.run(["-s", target, "reconnect", "offline"], timeout=15)
        return {
            "serial": target,
            "reconnected": rec.returncode == 0,
            "connect": ((rec.stdout or "") + (rec.stderr or "")).strip(),
        }

    def shell(self, command: str, timeout: int = 120) -> subprocess.CompletedProcess:
        if not self.serial:
            raise XianError("还没有选定设备。先运行 xian client discover")
        result = self.run(["-s", self.serial, "shell", command], timeout=timeout)
        if self._is_offline_output(result):
            self.reconnect(self.serial)
            result = self.run(["-s", self.serial, "shell", command], timeout=timeout)
        return result

    def pull(self, remote: str, local: Path, timeout: int = 180, allow_empty: bool = False) -> Path:
        if not self.serial:
            raise XianError("还没有选定设备")
        local = Path(local)
        local.parent.mkdir(parents=True, exist_ok=True)
        result = self.run(["-s", self.serial, "pull", remote, str(local)], timeout=timeout)
        if self._is_offline_output(result):
            self.reconnect(self.serial)
            result = self.run(["-s", self.serial, "pull", remote, str(local)], timeout=timeout)
        if result.returncode != 0 or not local.is_file():
            detail = ((result.stderr or "") + (result.stdout or "")).strip()
            raise XianError(f"拉取失败 {remote}：{detail[:300]}", code=3)
        if local.stat().st_size == 0 and not allow_empty:
            detail = ((result.stderr or "") + (result.stdout or "")).strip()
            raise XianError(f"拉取失败 {remote}：{detail[:300]}", code=3)
        return local

    def pull_tree(self, remote: str, local: Path, timeout: int = 7200) -> Path:
        if not self.serial:
            raise XianError("还没有选定设备")
        local = Path(local)
        local.parent.mkdir(parents=True, exist_ok=True)
        result = self.run(["-s", self.serial, "pull", remote, str(local)], timeout=timeout)
        if self._is_offline_output(result):
            self.reconnect(self.serial)
            result = self.run(["-s", self.serial, "pull", remote, str(local)], timeout=timeout)
        if not local.exists():
            detail = ((result.stderr or "") + (result.stdout or "")).strip()
            raise XianError(f"目录拉取失败 {remote}：{detail[:300]}", code=3)
        return local

    def devices(self) -> list[dict]:
        result = self.run(["devices", "-l"], timeout=20)
        rows = []
        for line in (result.stdout or "").splitlines():
            line = line.strip()
            if not line or line.startswith("List of"):
                continue
            parts = line.split()
            if len(parts) < 2:
                continue
            serial, state = parts[0], parts[1]
            model = ""
            for part in parts[2:]:
                if part.startswith("model:"):
                    model = part.split(":", 1)[1]
            rows.append({"serial": serial, "state": state, "model": model, "raw": line})
        return rows

    def connect(self, serial: str) -> str:
        result = self.run(["connect", serial], timeout=20)
        return ((result.stdout or "") + (result.stderr or "")).strip()

    def identity(self) -> dict:
        result = self.shell("id", timeout=15)
        text = (result.stdout or "").strip()
        return {
            "id": text,
            "root": text.startswith("uid=0"),
            "error": (result.stderr or "").strip(),
            "code": result.returncode,
        }

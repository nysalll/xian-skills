"""ADB process wrapper for device discovery, shell commands, and file pulls."""

from __future__ import annotations

import shutil
import subprocess
from pathlib import Path

from xian_skills.errors import EnvError, XianError


def which_adb(explicit: str = "") -> str | None:
    if explicit:
        path = Path(explicit)
        if path.is_file():
            return str(path)
        found = shutil.which(explicit)
        return found
    return shutil.which("adb")


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

    def shell(self, command: str, timeout: int = 120) -> subprocess.CompletedProcess:
        if not self.serial:
            raise XianError("还没有选定设备。先运行 xian client discover")
        return self.run(["-s", self.serial, "shell", command], timeout=timeout)

    def pull(self, remote: str, local: Path, timeout: int = 180, allow_empty: bool = False) -> Path:
        if not self.serial:
            raise XianError("还没有选定设备")
        local = Path(local)
        local.parent.mkdir(parents=True, exist_ok=True)
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

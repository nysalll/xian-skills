"""tcpdump control on a selected ADB device."""

from __future__ import annotations

import re
import shlex
import subprocess
import time
from pathlib import Path

from xian_skills.device.adb import Adb
from xian_skills.errors import XianError

_PCAP_NAME = re.compile(r"(.*\.pcap)(\d*)$")


def remote_prefix(session: str) -> str:
    safe = re.sub(r"[^A-Za-z0-9_-]", "_", session or "").strip("_-")[:40] or "session"
    return f"/data/local/tmp/zm_{safe}"


def ensure_root(adb: Adb) -> str:
    ident = adb.identity()
    if ident.get("root"):
        return ident["id"]
    adb.run(["-s", adb.serial, "root"], timeout=20)
    last = ident
    for _ in range(8):
        time.sleep(1)
        adb.connect(adb.serial)
        last = adb.identity()
        state = adb.run(["-s", adb.serial, "get-state"], timeout=15)
        if (state.stdout or "").strip() == "device" and last.get("root"):
            return last["id"]
    raise XianError(f"adb root 之后设备仍不是 root：{last}", code=2)


def pkill_tcpdump(adb: Adb) -> None:
    adb.shell("pkill tcpdump; sleep 1", timeout=20)


def tcpdump_alive(adb: Adb) -> bool:
    result = adb.shell("ps -A | grep tcpdump", timeout=15)
    return "tcpdump" in (result.stdout or "")


def start_tcpdump(adb: Adb, prefix: str, rotate_mb: int, force_single: bool = False):
    pkill_tcpdump(adb)
    adb.shell(f"rm -f {prefix}.pcap*", timeout=20)
    remote = f"{prefix}.pcap"
    attempts = []
    if not force_single:
        attempts.append((f"tcpdump -i any -nn -s 0 -U -B 4096 -C {int(rotate_mb)} -w {remote}", True))
        attempts.append((f"tcpdump -i any -nn -s 0 -C {int(rotate_mb)} -w {remote}", True))
        attempts.append((f"tcpdump -i any -s 0 -C {int(rotate_mb)} -w {remote}", True))
    attempts.append((f"tcpdump -i any -nn -s 0 -U -w {remote}", False))
    attempts.append((f"tcpdump -i any -s 0 -w {remote}", False))
    for command, rotate in attempts:
        proc = subprocess.Popen(
            [adb.exe, "-s", adb.serial, "shell", command],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
        time.sleep(2)
        if tcpdump_alive(adb):
            return proc, rotate
        if proc.poll() is None:
            proc.kill()
        pkill_tcpdump(adb)
    raise XianError("设备上没有把 tcpdump 拉起来。确认模拟器已 root，并且系统里有 tcpdump。", code=2)


def list_remote_pcaps(adb: Adb, prefix: str) -> list[tuple[int, str]]:
    result = adb.shell(f"ls -1 {prefix}.pcap* 2>/dev/null", timeout=20)
    expected_stem = Path(prefix).name + ".pcap"
    files = []
    for line in (result.stdout or "").splitlines():
        name = line.strip().replace("\\", "/")
        if not name or "*" in name or "No such" in name:
            continue
        base = name.split("/")[-1]
        if not base.startswith(expected_stem):
            continue
        match = _PCAP_NAME.match(base)
        if not match:
            continue
        index = int(match.group(2)) if match.group(2) else 0
        remote = f"{prefix}.pcap{index if index else ''}"
        files.append((index, remote))
    files.sort()
    return files


def rm_remote(adb: Adb, remote: str) -> None:
    if not remote.startswith("/data/local/tmp/zm_"):
        raise XianError(f"拒绝删除非抓包临时文件：{remote}")
    adb.shell(f"rm -f {shlex.quote(remote)}", timeout=20)

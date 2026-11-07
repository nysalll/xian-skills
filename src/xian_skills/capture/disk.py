"""Pause capture writes while a physical disk is saturated."""

from __future__ import annotations

import subprocess
import time

_PS = (
    "Get-CimInstance Win32_PerfFormattedData_PerfDisk_PhysicalDisk | "
    "Where-Object { $_.Name -ne '_Total' } | "
    "ForEach-Object { '{0}|{1}|{2}|{3}' -f $_.Name, $_.PercentDiskTime, "
    "$_.PercentDiskReadTime, $_.PercentDiskWriteTime }"
)


def disk_busy(threshold: int = 60) -> list[tuple[str, int]]:
    if subprocess.os.name != "nt":
        return []
    result = subprocess.run(
        ["powershell", "-NoProfile", "-Command", _PS],
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
    )
    busy = []
    for line in (result.stdout or "").splitlines():
        parts = line.strip().split("|")
        if len(parts) != 4:
            continue
        try:
            peak = max(int(float(part)) for part in parts[1:])
        except ValueError:
            continue
        if peak > threshold:
            busy.append((parts[0], peak))
    return busy


def wait_disk(threshold: int = 60, timeout: int = 90) -> bool:
    started = time.time()
    while True:
        if not disk_busy(threshold):
            return True
        if time.time() - started >= timeout:
            return False
        time.sleep(2)

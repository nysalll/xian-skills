"""Run the repository tests and record only the results that actually ran."""

from __future__ import annotations

import io
import os
import unittest
from pathlib import Path

BASIC_ON_PASS = (
    "environment",
    "client_sync",
    "lua_decode",
    "lua_tables",
    "query",
    "channel_diff",
    "protocol",
    "uplink",
    "logs",
    "assets_media",
    "mijing",
    "pvp",
    "update_report",
    "events",
)


def find_tests() -> Path | None:
    candidates = []
    env = os.environ.get("XIAN_ROOT")
    if env:
        candidates.append(Path(env))
    candidates.append(Path.cwd())
    candidates.extend(Path.cwd().parents)
    candidates.extend(Path(__file__).resolve().parents)
    seen = set()
    for parent in candidates:
        parent = Path(parent)
        if parent in seen:
            continue
        seen.add(parent)
        candidate = parent / "tests"
        marker = parent / "pyproject.toml"
        if marker.is_file() and candidate.is_dir() and "xian-skills" in marker.read_text(encoding="utf-8"):
            return candidate
    return None


def run_suite() -> dict:
    tests = find_tests()
    if tests is None:
        return {"ok": False, "error": "当前安装方式没有带上 tests 目录，不能把功能标成已测试。"}
    stream = io.StringIO()
    suite = unittest.defaultTestLoader.discover(str(tests))
    result = unittest.TextTestRunner(stream=stream, verbosity=1).run(suite)
    return {
        "ok": result.wasSuccessful(),
        "ran": result.testsRun,
        "failures": len(result.failures),
        "errors": len(result.errors),
        "tests": str(tests),
        "log_tail": stream.getvalue()[-3000:],
    }


def record_suite(data_dir: Path, result: dict) -> dict:
    from xian_skills.diagnostics.status import save_cap

    if result.get("ok"):
        for feature in BASIC_ON_PASS:
            save_cap(data_dir, feature, "basic_tested", f"unittest {result.get('ran')} passed")
    elif "ran" in result:
        save_cap(data_dir, "environment", "failed", f"unittest failures={result.get('failures')} errors={result.get('errors')}")
    return result

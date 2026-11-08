"""Regression checks from the second Windows + WorkBuddy install."""

from __future__ import annotations

import hashlib
import sys
import tempfile
import unittest
import zipfile
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from xian_skills.client.sync import parse_version_text
from xian_skills.device.adb import Adb
from xian_skills.device.select import adb_source, select_adb
from xian_skills.errors import NeedConfirm
from xian_skills.install.apply import PLATFORMS, make_zip
from xian_skills.tools.decompiler import RELEASE, file_sha256, inspect_exe, install


class SecondPcTests(unittest.TestCase):
    def test_version_file_lines_are_not_snapshot_counts(self):
        parsed = parse_version_text("1.0.1\n1.0.2\n")
        self.assertEqual(parsed["current_version"], "1.0.2")
        self.assertEqual(parsed["version_txt_line_count"], 2)
        self.assertIn("不是本机快照份数", parsed["note"])

    def test_decompiler_install_waits_for_yes_and_checks_hash(self):
        with self.assertRaises(NeedConfirm):
            install(cfg=None, yes=False)
        payload = b"not-the-release"
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "luajit-decompiler-v2.exe"
            path.write_bytes(payload)
            info = inspect_exe(path)
            self.assertFalse(info["sha256_ok"])
            self.assertEqual(info["sha256"], hashlib.sha256(payload).hexdigest())
            self.assertEqual(file_sha256(path), info["sha256"])
        self.assertEqual(len(RELEASE["sha256"]), 64)

    def test_running_adb_is_not_replaced(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            sdk = root / "Android" / "Sdk" / "platform-tools" / "adb.exe"
            mumu = root / "MuMu" / "shell" / "adb.exe"
            sdk.parent.mkdir(parents=True)
            mumu.parent.mkdir(parents=True)
            sdk.write_bytes(b"sdk")
            mumu.write_bytes(b"mumu")
            with patch("xian_skills.device.select.running_adb_exes", return_value=[str(mumu)]), patch(
                "xian_skills.device.select._candidate_adbs", return_value=[str(sdk), str(mumu)]
            ), patch("xian_skills.device.select.discover_endpoints", return_value=[]), patch.object(
                Adb, "devices", return_value=[{"serial": "127.0.0.1:16384", "state": "offline", "model": ""}]
            ):
                report = select_adb(str(sdk), auto_connect=False, replace=False)
            self.assertEqual(Path(report["adb"]), mumu)
            self.assertIn("offline", report["diagnosis"])
            self.assertEqual(adb_source(str(mumu)), "mumu")
            self.assertEqual(adb_source(str(sdk)), "android-sdk")

    def test_workbuddy_package_layout(self):
        self.assertEqual(PLATFORMS["workbuddy"]["user"], [".workbuddy/skills"])
        self.assertNotIn(".codebuddy/skills", PLATFORMS["workbuddy"]["project"])
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            skill = root / "skills" / "xian"
            skill.mkdir(parents=True)
            (skill / "SKILL.md").write_text("name: xian\n", encoding="utf-8")
            dest = root / "out.zip"
            make_zip(root / "skills", dest)
            names = zipfile.ZipFile(dest).namelist()
            self.assertIn("xian/SKILL.md", names)
            self.assertFalse(any(name.startswith("skills/") for name in names))


if __name__ == "__main__":
    unittest.main()

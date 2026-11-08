"""Synthetic coverage for recursive link queries, table completeness, and environment setup."""

from __future__ import annotations

import hashlib
import json
import os
import sys
import tempfile
import time
import unittest
import zipfile
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from xian_skills.cli.main import main
from xian_skills.client.sync import parse_version_text
from xian_skills.config.model import load_config, normalize_path_str
from xian_skills.device.adb import Adb
from xian_skills.device.select import adb_source, select_adb
from xian_skills.errors import NeedConfirm, XianError
from xian_skills.install.apply import PLATFORMS, make_zip
from xian_skills.lua.pipeline import export_tree
from xian_skills.query.ask import build_catalog, format_link_report, link_id
from xian_skills.tools.decompiler import RELEASE, file_sha256, inspect_exe, install


class QueryAndEnvTests(unittest.TestCase):
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
        launcher = Path(__file__).resolve().parents[1] / "installers" / "windows" / "xian.cmd"
        body = launcher.read_text(encoding="utf-8")
        self.assertIn('if exist "%LAUNCH%" set /p XIANEXE=<"%LAUNCH%"', body)
        self.assertIn('if defined XIANEXE if exist "%XIANEXE%"', body)

    def test_windows_path_and_config_backslash_handling(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            # Trailing quote left by Windows `\"` escaping on directory path
            self.assertEqual(normalize_path_str(f'"{root}\\"'), str(root))
            # PowerShell $env:VAR and %VAR% expansion
            with patch.dict(os.environ, {"XIAN_TEST_DIR": str(root)}):
                self.assertEqual(normalize_path_str("$env:XIAN_TEST_DIR\\sub"), str(root / "sub"))
                self.assertEqual(normalize_path_str("%XIAN_TEST_DIR%/sub"), str(root / "sub"))
            if os.name == "nt":
                self.assertEqual(normalize_path_str("/c/Users/demo/.xian-skills"), str(Path("C:/Users/demo/.xian-skills")))
            # Config file containing unescaped single backslashes (e.g. \Users, \tools)
            cfg_file = root / "config.json"
            cfg_file.write_text(
                '{\n  "schema": 1,\n  "decompiler_path": "C:\\Users\\player\\tools\\luajit-decompiler-v2.exe"\n}\n',
                encoding="utf-8",
            )
            cfg = load_config(cfg_file)
            self.assertTrue(cfg.data["decompiler_path"].endswith("luajit-decompiler-v2.exe"))

    def test_link_id_recursive_semantic_vs_value_matches(self):
        with tempfile.TemporaryDirectory() as tmp:
            tables = Path(tmp) / "official_tables"
            tables.mkdir(parents=True)

            # 1. Top-level primary key + multiple matches in same record + unrelated numeric value (combinable)
            (tables / "item.lua.json").write_text(
                json.dumps(
                    {
                        "data": {
                            "97104": {
                                "class_id": 97104,
                                "name": "合成点化玉",
                                "icon": 97104,
                                "combinable": 97104,
                                " active": True,
                            },
                            "1": {"class_id": 1, "flag": True},
                        }
                    },
                    ensure_ascii=False,
                ),
                encoding="utf-8",
            )
            # 2. String ID list inside a record (non-dict record value)
            (tables / "icon_path.lua.json").write_text(
                json.dumps({"data": {"/Item/": ["10001", "97104", "10002"]}}, ensure_ascii=False),
                encoding="utf-8",
            )
            # 3. Top-level list table + ordinary ID field + multi-level list (affix/cost tuples)
            (tables / "lingyu.lua.json").write_text(
                json.dumps(
                    {
                        "data": [
                            {
                                "id": 1,
                                "name": "测试领域",
                                "jade_item_id": 97104,
                                "unlock_cost": [[97104, 5], [1002, 97104]],
                            }
                        ]
                    },
                    ensure_ascii=False,
                ),
                encoding="utf-8",
            )
            # 4. Nested dict under ID-semantic key
            (tables / "lingyu_config.lua.json").write_text(
                json.dumps(
                    {
                        "data": {
                            "common": {
                                "lingyu_point_class_id": {"1": 97104, "2": 97105},
                                "hp": 97104,
                            }
                        }
                    },
                    ensure_ascii=False,
                ),
                encoding="utf-8",
            )
            # 5. Reward array of dicts + string-id reward pair
            (tables / "reward_part23.lua.json").write_text(
                json.dumps(
                    {
                        "data": {
                            "spirit_reward": [
                                {
                                    "reward_type": "spirit",
                                    "data": 97104,
                                    "amount": 1,
                                    "level_max": 97104,
                                }
                            ],
                            "loop_reward": [[97104, "loop_gift_1001"]],
                        }
                    },
                    ensure_ascii=False,
                ),
                encoding="utf-8",
            )
            # 6. Empty table, non-standard scalar record, and malformed JSON
            (tables / "empty.lua.json").write_text(json.dumps({"entries": 0, "data": {}}), encoding="utf-8")
            (tables / "scalar_row.lua.json").write_text(json.dumps({"data": {"raw_key": "other"}}), encoding="utf-8")
            (tables / "broken.lua.json").write_text("{not valid json 97104", encoding="utf-8")

            prov = {"channel": "official", "version": "1.0.26110401", "snapshot": "snap-official-1"}
            res_all = link_id(tables, "97104", prov, limit=50, mode="all")

            # Verify provenance and counts
            self.assertEqual(res_all["record_id"], "97104")
            self.assertEqual(res_all["unreadable_files"], 1)
            self.assertEqual(res_all["semantic_count"], 7)
            self.assertEqual(res_all["value_match_count"], 5)
            self.assertEqual(res_all["total_matches"], 12)

            sem_paths = {(h["table"], h["record_key"], h["field_path"], h["relation"]) for h in res_all["semantic_hits"]}
            self.assertIn(("item.lua.json", "97104", "class_id", "primary_key"), sem_paths)
            self.assertIn(("item.lua.json", "97104", "icon", "field"), sem_paths)
            self.assertIn(("icon_path.lua.json", "/Item/", "[1]", "field"), sem_paths)
            self.assertIn(("lingyu.lua.json", "0", "jade_item_id", "field"), sem_paths)
            self.assertIn(("lingyu.lua.json", "0", "unlock_cost[0][0]", "field"), sem_paths)
            self.assertIn(("lingyu_config.lua.json", "common", "lingyu_point_class_id.1", "field"), sem_paths)
            self.assertIn(("reward_part23.lua.json", "spirit_reward", "[0].data", "field"), sem_paths)

            val_paths = {(h["table"], h["record_key"], h["field_path"]) for h in res_all["value_matches"]}
            self.assertIn(("item.lua.json", "97104", "combinable"), val_paths)
            self.assertIn(("lingyu.lua.json", "0", "unlock_cost[1][1]"), val_paths)
            self.assertIn(("lingyu_config.lua.json", "common", "hp"), val_paths)
            self.assertIn(("reward_part23.lua.json", "spirit_reward", "[0].level_max"), val_paths)
            self.assertIn(("reward_part23.lua.json", "loop_reward", "[0][0]"), val_paths)

            for hit in res_all["hits"]:
                self.assertEqual(hit["source_channel"], "official")
                self.assertEqual(hit["source_version"], "1.0.26110401")
                self.assertEqual(hit["snapshot_id"], "snap-official-1")
                self.assertIn(hit["match_type"], ("semantic_reference", "value_match"))
                self.assertIn(hit["reference_confidence"], ("high", "medium", "low"))

            # Semantic mode returns only semantic_reference in hits
            res_sem = link_id(tables, 97104, prov, limit=50, mode="semantic")
            self.assertEqual(len(res_sem["hits"]), 7)
            self.assertTrue(all(h["match_type"] == "semantic_reference" for h in res_sem["hits"]))

            # Booleans never match integer 1
            res_one = link_id(tables, "1", prov, limit=50, mode="semantic")
            self.assertFalse(any(h["field_path"] == "flag" for h in res_one["hits"]))

            # Human-readable report
            text = format_link_report(res_all)
            self.assertIn("lingyu_point_class_id.1", text)
            self.assertIn("[候选关联]", text)

    def test_channel_isolation_depth_limit_and_performance(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            official_dir = root / "official" / "tables"
            zhengdao_dir = root / "zhengdao" / "tables"
            official_dir.mkdir(parents=True)
            zhengdao_dir.mkdir(parents=True)

            # Deeply nested structure exceeding max_depth=4
            deep = {"leaf_id": 88001}
            for _ in range(8):
                deep = {"nested": deep}
            (official_dir / "deep.lua.json").write_text(json.dumps({"data": {"1": deep}}), encoding="utf-8")
            (official_dir / "item.lua.json").write_text(
                json.dumps({"data": {"88001": {"class_id": 88001, "name": "正式服玉"}}}),
                encoding="utf-8",
            )
            (zhengdao_dir / "item.lua.json").write_text(
                json.dumps({"data": {"88001": {"class_id": 88001, "name": "证道服玉", "extra_id": 88001}}}),
                encoding="utf-8",
            )

            # Depth limit truncates safely without error
            shallow = link_id(official_dir, "88001", {"channel": "official", "version": "1.0.1", "snapshot": "s1"}, max_depth=4)
            self.assertEqual(len(shallow["hits"]), 1)
            self.assertGreater(shallow["truncated_depth"], 0)

            full_depth = link_id(official_dir, "88001", {"channel": "official", "version": "1.0.1", "snapshot": "s1"}, max_depth=16)
            self.assertEqual(len(full_depth["hits"]), 2)
            self.assertTrue(all(h["source_channel"] == "official" for h in full_depth["hits"]))

            # Catalog-based --link preserves channel isolation
            cat_dir = root / "official" / "catalog"
            build_catalog(official_dir, cat_dir, {"channel": "official", "version": "1.0.1", "snapshot": "s1"})
            code = main(["query", "--link", "88001", "--catalog", str(cat_dir), "--link-mode", "semantic", "--json"])
            self.assertEqual(code, 0)

            # Invalid inputs raise XianError
            with self.assertRaises(XianError):
                link_id(root / "nonexistent", "88001", {})
            with self.assertRaises(XianError):
                link_id(official_dir, "88001", {}, mode="invalid")
            with self.assertRaises(XianError):
                link_id(official_dir, "   ", {})

            # Large-scale synthetic performance check (250 tables)
            perf_dir = root / "perf_tables"
            perf_dir.mkdir()
            filler = json.dumps({"data": {str(i): {"id": i, "name": f"条目{i}", "cost": [i + 10, 5]} for i in range(1, 50)}})
            for t_idx in range(250):
                (perf_dir / f"table_{t_idx:03d}.lua.json").write_text(filler, encoding="utf-8")
            (perf_dir / "target.lua.json").write_text(
                json.dumps({"data": {"999999": {"class_id": 999999, "reward": [[999999, 1]]}}}),
                encoding="utf-8",
            )
            t0 = time.monotonic()
            perf_res = link_id(perf_dir, "999999", {"channel": "official", "version": "1.0.1", "snapshot": "s1"})
            elapsed = time.monotonic() - t0
            self.assertEqual(perf_res["semantic_count"], 2)
            self.assertLess(elapsed, 3.0)

    def test_table_export_distinguishes_runtime_generated_and_empty(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            src = root / "src"
            out = root / "tables"
            src.mkdir()
            (src / "static_tbl.lua").write_text('local t = { [1] = { id = 1, name = "静态" } }\nreturn t\n', encoding="utf-8")
            (src / "empty_tbl.lua").write_text("local t = {}\nreturn t\n", encoding="utf-8")
            (src / "runtime_tbl.lua").write_text(
                'local t = {}\ndo\n  local p = string.format("config_lua.runtime_tbl.runtime_tbl_part%d", 1)\n'
                "  function load_part() return rerequire(p) end\n  setmetatable(t, { __index = function() return nil end })\nend\nreturn t\n",
                encoding="utf-8",
            )
            (src / "logic_mod.lua").write_text("function helper(a, b)\n  return a + b\nend\n", encoding="utf-8")

            summary = export_tree(src, out)
            self.assertEqual(summary["ok"], 3)
            self.assertEqual(summary["nonempty"], 1)
            self.assertEqual(summary["runtime_generated"], 1)
            self.assertEqual(summary["empty"], 1)
            self.assertEqual(summary["logic_skipped"], 1)

            rt_json = json.loads((out / "runtime_tbl.lua.json").read_text(encoding="utf-8"))
            self.assertEqual(rt_json["data_status"], "runtime_generated")
            self.assertIn("runtime_tbl_part%d", rt_json["part_pattern"])

            cat_summary = build_catalog(out, root / "catalog", {"channel": "official", "version": "1.0.1", "snapshot": "s1"})
            self.assertEqual(cat_summary["nonempty_tables"], 1)
            self.assertEqual(cat_summary["runtime_generated_tables"], 1)
            self.assertEqual(cat_summary["empty_tables"], 1)


if __name__ == "__main__":
    unittest.main()

"""Synthetic coverage for the local toolchain. No private captures or game assets."""

from __future__ import annotations

import json
import os
import struct
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from xian_skills.cli.main import main
from xian_skills.events.analyze import analyze
from xian_skills.lua.decrypt import parse_lj_header, xor_m71
from xian_skills.lua.pipeline import build_index, dump_constants, export_table
from xian_skills.protocol.redact import redact
from xian_skills.query.engine import query_index, query_table
from xian_skills.research.mijing import invert_resist, summarize_jsonl, wilson
from xian_skills.research.plan import init_script, plan
from xian_skills.research.pvp import crit_rate, evaluate, hit_rate
from xian_skills.client.sync import _journal_hit, parse_size_list
from xian_skills.storage.warehouse import diff_manifests, import_tree, latest_complete
from xian_skills.storage.warehouse import Warehouse
from xian_skills.updates.report import report_from_tables


LUA = """
local __default_values = { rarity = 1 }
local key2idx = { name = 1, count = 2 }
local rows = {
  [1001] = { name = "测试丹", count = 3, reward = {2001, 2}, cost = {3001, 5} },
  [1002] = { name = "测试符" },
}
return rows
"""


class PipelineTests(unittest.TestCase):
    def test_chunk_name_uses_length_prefix(self):
        name = b"@config_lua\\item.lua"
        data = b"\x1bLJ\x02\x08" + bytes([len(name)]) + name + b"\x22\x00rest"
        self.assertEqual(parse_lj_header(data)["path"], "@config_lua\\item.lua")

    def test_xor_roundtrip_and_constants_reject_plain(self):
        raw = b"\x1bLJ demo"
        self.assertEqual(xor_m71(xor_m71(raw)), raw)
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "plain.lua"
            path.write_bytes(b"return {1}")
            dumped = dump_constants(path)
            self.assertEqual(dumped["error"], "not luajit")

    def test_table_index_query(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            lua = root / "activity_gift.lua"
            lua.write_text(LUA, encoding="utf-8")
            exported = export_table(lua, root / "tables" / "activity_gift.lua.json")
            self.assertTrue(exported["ok"])
            indexed = build_index(root, root / "tables", root / "index")
            self.assertGreaterEqual(indexed["tables"], 1)
            found = query_index(root / "index", "table", "activity")
            self.assertEqual(found["count"], 1)
            filtered = query_table(root / "tables" / "activity_gift.lua.json", "count", "eq", "3")
            self.assertEqual(filtered["hits"][0]["id"], "1001")
            code = main(["search", "--root", str(root), "--q", "测试丹", "--json"])
            self.assertEqual(code, 0)

    def test_events_and_update_report(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            left = root / "left"
            right = root / "right"
            left.mkdir()
            right.mkdir()
            payload = {
                "data": {
                    "1": {"name": "月活动", "reward": [{"id": 9, "count": 2}], "cost": [8, 4]},
                }
            }
            (right / "festival_activity.json").write_text(json.dumps(payload), encoding="utf-8")
            (left / "old.json").write_text("{}", encoding="utf-8")
            report = analyze(right, left)
            self.assertTrue(report["activities"])
            self.assertEqual({item["count"] for item in report["activities"][0]["items"]}, {2, 4})
            out = root / "report.md"
            result = report_from_tables(left, right, out)
            self.assertTrue(out.is_file())
            self.assertGreater(result["diff"]["added"], 0)


class WarehouseTests(unittest.TestCase):
    def test_import_keeps_history_and_reuses_blobs(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            src = root / "src"
            (src / "Lua64").mkdir(parents=True)
            (src / "version.txt").write_text("1.0.1\n1.0.2\n", encoding="utf-8")
            (src / "Lua64" / "a.unity3d").write_bytes(b"same")
            warehouse = Warehouse(root / "data")
            first = import_tree(warehouse, "official", "1.0.2", src)
            (src / "Lua64" / "b.unity3d").write_bytes(b"new")
            second = import_tree(warehouse, "official", "1.0.2", src)
            os.environ["XIAN_HOME"] = str(root / "home")
            os.environ["XIAN_DATA"] = str(warehouse.root)
            left = warehouse.read_snapshot("official", first["id"])
            right = warehouse.read_snapshot("official", second["id"])
            diff = diff_manifests(left, right)
            self.assertIn("Lua64/b.unity3d", diff["added"])
            blob_files = [path for path in (warehouse.root / "blobs").rglob("*") if path.is_file()]
            self.assertEqual(len(blob_files), 3)
            shared = [item for item in right["files"] if item["rel"] == "Lua64/a.unity3d"][0]["sha256"]
            self.assertTrue(warehouse.has_blob(shared))
            code = main(["cache", "clean", "--yes", "--json"])
            self.assertEqual(code, 0)
            self.assertTrue(warehouse.has_blob(shared))
            self.assertEqual(latest_complete(warehouse, "official")["id"], second["id"])


class SnapshotRuleTests(unittest.TestCase):
    def test_partial_snapshot_is_not_a_full_version(self):
        with tempfile.TemporaryDirectory() as tmp:
            warehouse = Warehouse(Path(tmp))
            warehouse.ensure()
            warehouse.commit_snapshot(
                "official",
                "partial",
                {
                    "collected_at": "20260101T000000Z",
                    "complete": False,
                    "incomplete": True,
                    "files": [{"rel": "version.txt", "sha256": "a", "size": 1, "md5": "old"}],
                },
            )
            blob = warehouse.root / "blobs" / "aa" / "aa"
            blob.parent.mkdir(parents=True)
            blob.write_bytes(b"x")
            self.assertIsNone(
                _journal_hit(
                    {},
                    {"version.txt": {"sha256": "aa", "size": 4, "md5": "old"}},
                    "version.txt",
                    4,
                    "new",
                    warehouse,
                )
            )
            self.assertIsNone(
                _journal_hit(
                    {},
                    {"version.txt": {"sha256": "aa", "size": 4, "md5": "old"}},
                    "version.txt",
                    4,
                    None,
                    warehouse,
                )
            )
            warehouse.commit_snapshot(
                "official",
                "fullone",
                {
                    "collected_at": "20260102T000000Z",
                    "complete": True,
                    "incomplete": False,
                    "files": [{"rel": "version.txt", "sha256": "aa", "size": 1}],
                },
            )
            self.assertEqual(latest_complete(warehouse, "official")["id"], "fullone")
            self.assertEqual(parse_size_list("9|./Lua64/a.unity3d\n")["Lua64/a.unity3d"], 9)


class CatalogTests(unittest.TestCase):
    def test_question_stays_inside_one_catalog(self):
        from xian_skills.query.ask import ask
        from xian_skills.updates.records import diff_records, same_channel_history

        catalog = {
            "channel": "official",
            "version": "1.0.1",
            "snapshot": "snap-a",
            "names": [{"table": "item.lua.json", "id": "9", "field": "name", "value": "测试丹"}],
            "tables": [{"rel": "activity_loop_config.lua.json", "entries": 2, "fields": ["reward"], "path": "a"}],
        }
        found = ask(catalog, "查一下测试丹和活动")
        self.assertEqual(found["name_hits"][0]["channel"], "official")
        self.assertEqual(found["name_hits"][0]["snapshot"], "snap-a")
        self.assertTrue(found["table_hits"])
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            left = root / "left.json"
            right = root / "right.json"
            left.write_text(json.dumps({"data": {"1": {"name": "甲", "count": 1}, "2": {"name": "乙"}}}), encoding="utf-8")
            right.write_text(json.dumps({"data": {"1": {"name": "甲", "count": 2}, "3": {"name": "丙"}}}), encoding="utf-8")
            diff = diff_records(left, right)
            self.assertEqual(diff["added"], 1)
            self.assertEqual(diff["removed"], 1)
            self.assertEqual(diff["changed"], 1)
        history = same_channel_history([{"complete": True, "version": "1.0.1"}, {"complete": True, "version": "1.0.1"}])
        self.assertFalse(history["comparable"])


class ResearchTests(unittest.TestCase):
    def test_pvp_and_mijing_math(self):
        expected_hit = 500000 / (500000 * 0.9 + 400000 * 0.15) * 100
        self.assertAlmostEqual(hit_rate(500000, 400000), expected_hit)
        self.assertLess(crit_rate(900000, 700000), 50)
        result = evaluate({"hitrate": 500000, "dodge": 400000, "crit": 900000, "crit_resist": 700000})
        self.assertIn("limitation", result)
        rate, low, high = wilson(8, 20)
        self.assertIsNotNone(rate)
        self.assertLess(low, high)
        self.assertAlmostEqual(invert_resist(1000, 0.2), 0.26 * 1000 * 0.8 / (0.2 + 0.8 * 0.2))
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "cap.jsonl"
            path.write_text(
                "\n".join(
                    [
                        json.dumps({"msg": ["appear", {"rid": "m1", "type": "monster", "name": "木桩"}]}),
                        json.dumps({"msg": ["attrib_update", ["me", "crit_chance", 0, 1000, "combat_user"]]}),
                        json.dumps({"msg": ["skill_hit", ["me", 1, 1, "m1", 100, 0, 0, [True]]]}),
                        json.dumps({"msg": ["skill_hit", ["me", 1, 1, "m1", 80, 0, 0, [False]]]}),
                    ]
                ),
                encoding="utf-8",
            )
            summary = summarize_jsonl(path, me="me")
            self.assertEqual(summary["hits"], 2)
            self.assertEqual(summary["crits"], 1)
            self.assertEqual(summary["monsters"], 1)
            study = init_script(Path(tmp) / "research", "神通伤害")
            self.assertTrue((Path(study["dir"]) / "RESULT.md").is_file())
        planned = plan("帮我研究某个神通的会心和伤害")
        self.assertIn("pvp", planned["tags"])
        self.assertIn("已确认事实", planned["must_separate"])


class ProtocolTests(unittest.TestCase):
    def test_redact(self):
        cleaned = redact({"msg": ["login", {"password": "secret", "name": "visible"}], "_body_hex": "aabb"})
        self.assertEqual(cleaned["msg"][1]["password"], "[redacted]")
        self.assertEqual(cleaned["msg"][1]["name"], "visible")
        self.assertEqual(cleaned["_body_hex"], "[ciphertext-omitted]")

    def test_frame_and_uplink(self):
        try:
            import msgpack
        except ImportError:
            self.skipTest("msgpack not installed")
        from xian_skills.capture.session import parse_capture
        from xian_skills.protocol.zm import _decrypt_msg, _key_bytes

        body = msgpack.packb(["ping"])
        frame = b"ZM" + struct.pack(">II", 7, len(body)) + body
        tcp = struct.pack(">HHIIBBHHH", 11111, 9000, 1, 0, 5 << 4, 0x18, 65535, 0, 0) + frame
        ip = struct.pack(">BBHHHBBH4B4B", 0x45, 0, 20 + len(tcp), 0, 0, 64, 6, 0, 10, 0, 0, 2, 1, 2, 3, 4)
        packet = b"\x00" * 12 + b"\x08\x00" + ip + tcp
        header = struct.pack("<IHHIIII", 0xA1B2C3D4, 2, 4, 0, 0, 65535, 1)
        record = struct.pack("<IIII", 1, 0, len(packet), len(packet)) + packet
        with tempfile.TemporaryDirectory() as tmp:
            pcap = Path(tmp) / "sample.pcap"
            out = Path(tmp) / "out.jsonl"
            pcap.write_bytes(header + record)
            parsed = parse_capture(pcap, out)
            self.assertGreaterEqual(parsed["frames"], 1)
            saved = json.loads(out.read_text(encoding="utf-8").splitlines()[0])
            self.assertEqual(saved["msg"][0], "ping")
        key = _key_bytes(1700000000, "Abc34567890123456")
        self.assertEqual(len(key), 16)
        try:
            from Crypto.Cipher import AES
        except ImportError:
            self.skipTest("pycryptodome not installed")
        plain_body = msgpack.packb(["hello"])
        plain = bytes([1, 2, 1, 2]) + struct.pack(">I", len(plain_body)) + plain_body
        plain += b"\x00" * ((16 - len(plain) % 16) % 16)
        encrypted = b"cr" + AES.new(key, AES.MODE_ECB).encrypt(plain)
        self.assertEqual(_decrypt_msg(key, encrypted)[0], "hello")


class AssetTests(unittest.TestCase):
    def test_usm_header(self):
        from xian_skills.assets.usm import demux_one

        payload = b"DKIF" + b"\x00" * 28
        hsz = 2
        size = 10 + len(payload)
        blob = b"@SFV" + struct.pack(">I", size) + struct.pack(">H", hsz) + payload
        with tempfile.TemporaryDirectory() as tmp:
            src = Path(tmp) / "demo.usm"
            src.write_bytes(blob)
            result = demux_one(str(src), str(Path(tmp) / "out"))
            self.assertEqual(result["status"], "ok")
            self.assertTrue((Path(tmp) / "out" / "demo.ivf").is_file())


class CliTests(unittest.TestCase):
    def setUp(self):
        self._env = os.environ.copy()
        self.tmp = tempfile.TemporaryDirectory()
        os.environ["XIAN_HOME"] = self.tmp.name
        os.environ["XIAN_DATA"] = str(Path(self.tmp.name) / "data")

    def tearDown(self):
        os.environ.clear()
        os.environ.update(self._env)
        self.tmp.cleanup()

    def test_help_confirm_and_doctor(self):
        with self.assertRaises(SystemExit) as ctx:
            main(["--help"])
        self.assertEqual(ctx.exception.code, 0)
        self.assertEqual(main(["capture", "start", "--session", "demo", "--json"]), 4)
        self.assertEqual(main(["runtime", "probe", "--json"]), 4)
        self.assertEqual(main(["doctor", "--no-device", "--json"]), 0)
        self.assertEqual(main(["init", "--json"]), 0)
        self.assertTrue((Path(self.tmp.name) / "config.json").is_file())

    def test_install_is_non_destructive(self):
        from xian_skills.install.apply import install_skills, skills_source

        home = Path(self.tmp.name) / "home"
        project = Path(self.tmp.name) / "project"
        source = skills_source()
        existing = home / ".cursor" / "skills" / "xian"
        existing.mkdir(parents=True)
        (existing / "SKILL.md").write_text("---\nname: xian\ndescription: keep\n---\nkeep\n", encoding="utf-8")
        report = install_skills(source, home, project, ["cursor"], force=False, backup_root=Path(self.tmp.name) / "backup")
        self.assertIn("skipped-existing", {row["status"] for row in report["results"]})
        self.assertIn("keep", (existing / "SKILL.md").read_text(encoding="utf-8"))
        self.assertFalse(report["invocation_verified"])


if __name__ == "__main__":
    unittest.main()

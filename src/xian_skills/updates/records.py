"""Record-level comparison. Cross-channel output is not a same-channel patch note."""

from __future__ import annotations

import json
from pathlib import Path

from xian_skills.errors import XianError

SYSTEM_TOKENS = (
    ("道具", ("item",)),
    ("奖励", ("reward",)),
    ("活动", ("activity", "huodong")),
    ("神通", ("shentong", "skill")),
    ("功法", ("gongfa", "xinfa")),
    ("战斗系数", ("calc",)),
)


def _load(path: Path):
    payload = json.loads(path.read_text(encoding="utf-8"))
    if isinstance(payload, dict) and isinstance(payload.get("data"), dict):
        return payload["data"]
    if isinstance(payload, dict):
        return payload
    raise XianError(f"无法按记录比较：{path}")


def _system(rel: str) -> str:
    text = rel.lower()
    for label, tokens in SYSTEM_TOKENS:
        if any(token in text for token in tokens):
            return label
    return "未按文件名归类"


def diff_records(left: Path, right: Path, sample: int = 20) -> dict:
    left_data = _load(Path(left))
    right_data = _load(Path(right))
    left_ids = set(map(str, left_data))
    right_ids = set(map(str, right_data))
    added = sorted(right_ids - left_ids)
    removed = sorted(left_ids - right_ids)
    changed = []
    for key in sorted(left_ids & right_ids):
        old = left_data.get(key) if key in left_data else left_data.get(int(key) if key.isdigit() else key)
        new = right_data.get(key) if key in right_data else right_data.get(int(key) if key.isdigit() else key)
        if old == new:
            continue
        fields = []
        if isinstance(old, dict) and isinstance(new, dict):
            fields = sorted(str(field) for field in set(old) | set(new) if old.get(field) != new.get(field))
        changed.append({"id": key, "fields": fields[:12]})
    return {
        "added": len(added),
        "removed": len(removed),
        "changed": len(changed),
        "added_ids": added[:sample],
        "removed_ids": removed[:sample],
        "changed_sample": changed[:sample],
    }


def diff_table_tree(left: Path, right: Path, left_meta: dict, right_meta: dict, relation: str) -> dict:
    left = Path(left)
    right = Path(right)
    if not left.is_dir():
        raise XianError(f"左侧目录不存在：{left}")
    if not right.is_dir():
        raise XianError(f"右侧目录不存在：{right}")
    left_files = {path.relative_to(left).as_posix(): path for path in left.rglob("*.json") if path.is_file() and not path.name.startswith("_")}
    right_files = {path.relative_to(right).as_posix(): path for path in right.rglob("*.json") if path.is_file() and not path.name.startswith("_")}
    rows = []
    for rel in sorted(set(left_files) | set(right_files)):
        if rel not in left_files:
            rows.append({"table": rel, "system": _system(rel), "status": "added"})
            continue
        if rel not in right_files:
            rows.append({"table": rel, "system": _system(rel), "status": "removed"})
            continue
        try:
            detail = diff_records(left_files[rel], right_files[rel])
        except (OSError, json.JSONDecodeError, XianError) as exc:
            rows.append({"table": rel, "system": _system(rel), "status": "unreadable", "error": str(exc)})
            continue
        if detail["added"] or detail["removed"] or detail["changed"]:
            rows.append({"table": rel, "system": _system(rel), "status": "changed", **detail})
    return {
        "relation": relation,
        "left": left_meta,
        "right": right_meta,
        "warning": (
            "这是两个渠道同一时期客户端的横向差异，不能把它写成某一边的历史更新说明。"
            if relation == "cross-channel"
            else "这是同一渠道两份快照的比较。"
        ),
        "tables": rows,
    }


def same_channel_history(snapshots: list[dict]) -> dict:
    versions = []
    for snap in snapshots:
        if snap.get("complete") is not True or snap.get("incomplete"):
            continue
        version = snap.get("version")
        if version and version not in versions:
            versions.append(version)
    return {
        "comparable": len(versions) >= 2,
        "versions": versions,
        "reason": None if len(versions) >= 2 else "同一渠道目前只有一个完整客户端版本，不能把它和另一个渠道的差异说成历史更新。",
    }


def to_markdown(report: dict) -> str:
    lines = [
        "# 配置差异",
        "",
        f"- 关系：{report['relation']}",
        f"- 左侧：{report['left']}",
        f"- 右侧：{report['right']}",
        f"- {report['warning']}",
        "",
    ]
    for row in report["tables"]:
        if row["status"] == "changed":
            lines.append(
                f"- {row['system']} `{row['table']}` 新增记录 {row['added']}，删除 {row['removed']}，字段变化 {row['changed']}"
            )
        else:
            lines.append(f"- {row['system']} `{row['table']}` {row['status']}")
    if not report["tables"]:
        lines.append("- 已比较的表没有记录差异。")
    lines.append("")
    return "\n".join(lines)

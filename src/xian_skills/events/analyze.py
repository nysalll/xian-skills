"""Find activity-like tables and add up configured costs and rewards."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

from xian_skills.errors import XianError

HINTS = (
    "activity",
    "event",
    "huodong",
    "gift",
    "reward",
    "shop",
    "exchange",
    "mission",
    "task",
    "sign",
    "lottery",
    "pool",
    "turn",
    "festival",
)
REWARD_KEYS = {"reward", "rewards", "award", "awards", "gain", "bonus", "drop"}
COST_KEYS = {"cost", "costs", "price", "consume", "need", "exchange_cost", "ticket"}
COUNT_KEYS = ("count", "num", "amount", "value", "qty")
ID_KEYS = ("id", "item_id", "class_id", "item", "cfg_id")


def _payload(path: Path):
    data = json.loads(path.read_text(encoding="utf-8"))
    if isinstance(data, dict) and "data" in data and isinstance(data["data"], (dict, list)):
        return data["data"]
    return data


def _score(path: Path, sample_keys: list[str]) -> int:
    text = path.as_posix().lower() + " " + " ".join(sample_keys).lower()
    return sum(1 for hint in HINTS if hint in text)


def _as_item(value):
    if isinstance(value, dict):
        item_id = next((value.get(key) for key in ID_KEYS if key in value), None)
        count = next((value.get(key) for key in COUNT_KEYS if key in value), None)
        if item_id is not None and count is not None:
            return {"id": item_id, "count": count}
    if isinstance(value, list) and len(value) >= 2 and not isinstance(value[0], (dict, list)):
        if isinstance(value[0], (int, float)) and not isinstance(value[0], bool) and isinstance(value[1], str):
            return {"id": value[1], "count": value[0]}
        return {"id": value[0], "count": value[1]}
    return None


def _collect(node, bucket: list, depth: int = 0):
    if depth > 5:
        return
    if isinstance(node, dict):
        for key, value in node.items():
            if str(key).lower() in REWARD_KEYS or str(key).lower() in COST_KEYS:
                kind = "reward" if str(key).lower() in REWARD_KEYS else "cost"
                found = _as_item(value)
                if found:
                    bucket.append({**found, "kind": kind, "field": key})
                elif isinstance(value, list):
                    for item in value:
                        found = _as_item(item)
                        if found:
                            bucket.append({**found, "kind": kind, "field": key})
                        else:
                            _collect(item, bucket, depth + 1)
                else:
                    _collect(value, bucket, depth + 1)
            else:
                _collect(value, bucket, depth + 1)
    elif isinstance(node, list):
        for item in node[:200]:
            _collect(item, bucket, depth + 1)


def _names(root: Path) -> dict:
    names = {}
    for path in root.rglob("*.json"):
        try:
            data = _payload(path)
        except (OSError, json.JSONDecodeError):
            continue
        rows = data.values() if isinstance(data, dict) else data if isinstance(data, list) else []
        for row in list(rows)[:5000]:
            if not isinstance(row, dict):
                continue
            if "name" not in row:
                continue
            for key in ID_KEYS:
                if key in row:
                    names[str(row[key])] = row["name"]
                    break
    return names


def analyze(tables: Path, other: Path | None = None) -> dict:
    tables = Path(tables)
    if not tables.is_dir():
        raise XianError(f"配置目录不存在：{tables}")
    names = _names(tables)
    activities = []
    for path in sorted(tables.rglob("*.json")):
        try:
            data = _payload(path)
        except (OSError, json.JSONDecodeError):
            continue
        sample = {}
        if isinstance(data, dict) and data:
            first = next(iter(data.values()))
            if isinstance(first, dict):
                sample = first
        score = _score(path, list(sample.keys()))
        if score <= 0:
            continue
        items = []
        _collect(data, items)
        totals: dict[str, dict] = {}
        for item in items:
            try:
                amount = float(item["count"])
            except (TypeError, ValueError):
                continue
            slot = totals.setdefault(
                f"{item['kind']}:{item['id']}",
                {"kind": item["kind"], "id": item["id"], "count": 0, "name": names.get(str(item["id"]))},
            )
            slot["count"] += amount
        activities.append(
            {
                "table": path.relative_to(tables).as_posix(),
                "score": score,
                "fields": [str(key) for key in list(sample.keys())[:30]],
                "items": list(totals.values()),
            }
        )
    activities.sort(key=lambda row: (-row["score"], row["table"]))
    report = {
        "activities": activities,
        "assumptions": [
            "只统计配置里能识别的奖励和消耗字段。",
            "没有把概率奖励折算成期望，除非字段本身就是确定数量。",
            "服务器限购、个人进度和未公开随机不在这份结果里。",
        ],
        "evidence": "client_tables",
    }
    if other and Path(other).is_dir():
        report["channel_diff"] = _diff_dirs(tables, Path(other))
    return report


def _digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _diff_dirs(left: Path, right: Path) -> dict:
    left_files = {path.relative_to(left).as_posix(): path for path in left.rglob("*.json")}
    right_files = {path.relative_to(right).as_posix(): path for path in right.rglob("*.json")}
    added = sorted(set(right_files) - set(left_files))
    removed = sorted(set(left_files) - set(right_files))
    changed = sorted(
        rel for rel in set(left_files) & set(right_files) if _digest(left_files[rel]) != _digest(right_files[rel])
    )
    return {"added": added, "removed": removed, "changed": changed}


def to_markdown(report: dict) -> str:
    lines = ["# 活动配置分析", "", "证据级别：客户端配置。下面的数量是配置里能加总的数字，不是已经发生的个人收益。", ""]
    for row in report.get("activities") or []:
        lines.append(f"## {row['table']}")
        lines.append("")
        if row["items"]:
            for item in row["items"]:
                label = item.get("name") or item["id"]
                lines.append(f"- {item['kind']} {label}：{item['count']}")
        else:
            lines.append("- 找到活动相关表，但没有识别出可加总的奖励或消耗。")
        lines.append("")
    lines.append("## 假设与限制")
    lines.append("")
    for item in report.get("assumptions") or []:
        lines.append(f"- {item}")
    diff = report.get("channel_diff")
    if diff:
        lines.extend(["", "## 两侧差异", "", f"- 新增 {len(diff['added'])}", f"- 删除 {len(diff['removed'])}", f"- 内容变化 {len(diff['changed'])}"])
    lines.append("")
    return "\n".join(lines)

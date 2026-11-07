"""Composable queries over indexes and exported tables."""

from __future__ import annotations

import json
import operator
import re
from pathlib import Path

from xian_skills.errors import XianError

OPS = {
    "eq": operator.eq,
    "ne": operator.ne,
    "gt": operator.gt,
    "ge": operator.ge,
    "lt": operator.lt,
    "le": operator.le,
    "contains": lambda left, right: right in left if isinstance(left, str) else right in str(left),
}


def _load_json(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


def _table_payload(path: Path):
    payload = _load_json(path)
    if isinstance(payload, dict) and "data" in payload:
        return payload["data"]
    return payload


def query_index(index_dir: Path, kind: str, text: str, limit: int = 50) -> dict:
    index_dir = Path(index_dir)
    master_path = index_dir / "master_index.json"
    func_path = index_dir / "function_index.json"
    if not master_path.is_file():
        raise XianError(f"没有索引：{master_path}。先运行 xian lua index")
    master = _load_json(master_path)
    needle = text.lower()
    hits = []
    if kind == "file":
        hits = [row for row in master.get("files") or [] if needle in row["rel"].lower()]
    elif kind == "table":
        hits = [row for row in master.get("tables") or [] if needle in row["rel"].lower()]
    elif kind == "field":
        for row in master.get("tables") or []:
            matched = [field for field in row.get("fields") or [] if needle in field.lower()]
            if matched:
                hits.append({**row, "matched_fields": matched})
    elif kind == "func":
        functions = _load_json(func_path) if func_path.is_file() else {}
        for name, locs in functions.items():
            if needle in name.lower():
                hits.append({"name": name, "locations": locs[:8], "count": len(locs)})
    else:
        raise XianError("kind 必须是 file、table、field 或 func")
    return {"kind": kind, "q": text, "count": len(hits), "hits": hits[:limit]}


def _number(text: str):
    try:
        if "." in text:
            return float(text)
        return int(text)
    except ValueError:
        return text


def query_table(path: Path, field: str | None, op: str | None, value: str | None, limit: int = 50) -> dict:
    data = _table_payload(Path(path))
    if not isinstance(data, dict):
        raise XianError("表数据不是对象，无法按字段筛选")
    rows = []
    compare = OPS.get(op or "eq")
    if op and compare is None:
        raise XianError(f"不支持的比较 {op}")
    expected = _number(value) if value is not None else None
    for key, row in data.items():
        if field is None:
            rows.append({"id": key, "row": row})
        elif isinstance(row, dict) and field in row:
            current = row[field]
            if op is None or compare(current, expected):
                rows.append({"id": key, "value": current, "row": row})
        if len(rows) >= limit:
            break
    return {"table": str(path), "count": len(rows), "hits": rows}


def search_text(root: Path, text: str, limit: int = 40) -> dict:
    root = Path(root)
    if not root.exists():
        raise XianError(f"搜索目录不存在：{root}")
    hits = []
    rx = re.compile(re.escape(text), re.I)
    for path in root.rglob("*"):
        if not path.is_file():
            continue
        if path.suffix.lower() not in {".lua", ".json", ".txt", ".md"}:
            continue
        if path.stat().st_size > 8_000_000:
            continue
        try:
            body = path.read_text(encoding="utf-8", errors="ignore")
        except OSError:
            continue
        if rx.search(body):
            hits.append(str(path))
        if len(hits) >= limit:
            break
    return {"q": text, "count": len(hits), "hits": hits}

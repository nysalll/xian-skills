"""Search exported tables without mixing channels or versions."""

from __future__ import annotations

import json
import re
from pathlib import Path

from xian_skills.errors import XianError

NAME_FIELDS = {"name", "title", "skill_name", "show_name"}
TOPICS = (
    ("神通", ("shentong", "skill")),
    ("功法", ("gongfa", "xinfa", "inner_skill")),
    ("道具", ("item",)),
    ("物品", ("item",)),
    ("活动", ("activity", "huodong")),
    ("奖励", ("reward",)),
    ("兑换", ("exchange", "shop")),
    ("任务", ("mission", "task")),
    ("月活动", ("activity", "month")),
)
TOPIC_WORDS = {word for word, _tokens in TOPICS}


def build_catalog(tables: Path, dest: Path, provenance: dict) -> dict:
    tables = Path(tables)
    dest = Path(dest)
    if not tables.is_dir():
        raise XianError(f"导表目录不存在：{tables}")
    dest.mkdir(parents=True, exist_ok=True)
    table_rows = []
    names = []
    for path in sorted(tables.rglob("*.json")):
        if path.name.startswith("_"):
            continue
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            continue
        data = payload.get("data") if isinstance(payload, dict) and "data" in payload else payload
        rel = path.relative_to(tables).as_posix()
        fields = []
        if isinstance(data, dict) and data:
            sample = next((value for value in data.values() if isinstance(value, dict)), None)
            if sample:
                fields = [str(key) for key in list(sample.keys())[:40]]
            for key, row in data.items():
                if not isinstance(row, dict):
                    continue
                for field in NAME_FIELDS:
                    value = row.get(field)
                    if isinstance(value, str) and value.strip():
                        names.append({"table": rel, "id": str(key), "field": field, "value": value})
        table_rows.append(
            {
                "rel": rel,
                "entries": len(data) if isinstance(data, dict) else 0,
                "fields": fields,
                "path": str(path),
            }
        )
    catalog = {
        "channel": provenance.get("channel"),
        "version": provenance.get("version"),
        "snapshot": provenance.get("snapshot"),
        "tables_dir": str(tables),
        "tables": table_rows,
        "names": names,
    }
    (dest / "catalog.json").write_text(json.dumps(catalog, ensure_ascii=False), encoding="utf-8")
    return {
        "dir": str(dest),
        "tables": len(table_rows),
        "names": len(names),
        "channel": catalog["channel"],
        "version": catalog["version"],
        "snapshot": catalog["snapshot"],
    }


def load_catalog(path: Path) -> dict:
    path = Path(path)
    if path.is_dir():
        path = path / "catalog.json"
    if not path.is_file():
        raise XianError(f"没有目录索引：{path}")
    return json.loads(path.read_text(encoding="utf-8"))


_STOP = ("查一下", "帮我", "查询", "看看", "分析", "什么", "哪些", "一下", "配置", "的", "和", "与", "中")


def _terms(question: str) -> tuple[list[str], list[str]]:
    text = question or ""
    tokens = []
    for word, words in TOPICS:
        if word in text:
            tokens.extend(words)
            text = text.replace(word, " ")
    for word in _STOP:
        text = text.replace(word, " ")
    literals = [piece for piece in re.findall(r"[\u4e00-\u9fffA-Za-z0-9_]{2,}", text) if piece not in TOPIC_WORDS]
    return literals, tokens


def _name_match(question: str, value: str, literals: list[str]) -> bool:
    if len(value) >= 2 and value in (question or ""):
        return True
    return any(len(literal) >= 2 and literal.lower() in value.lower() for literal in literals)


def ask(catalog: dict, question: str, limit: int = 20) -> dict:
    literals, tokens = _terms(question)
    provenance = {
        "channel": catalog.get("channel"),
        "version": catalog.get("version"),
        "snapshot": catalog.get("snapshot"),
    }
    name_hits = []
    for row in catalog.get("names") or []:
        text = row.get("value") or ""
        if _name_match(question, text, literals):
            name_hits.append({**provenance, **row})
            if len(name_hits) >= limit:
                break
    table_hits = []
    needles = [token.lower() for token in tokens + literals]
    for row in catalog.get("tables") or []:
        rel = row["rel"].lower()
        fields = [field.lower() for field in row.get("fields") or []]
        if any(needle and (needle in rel or any(needle in field for field in fields)) for needle in needles):
            table_hits.append({**provenance, "table": row["rel"], "entries": row["entries"], "fields": row["fields"], "path": row["path"]})
            if len(table_hits) >= limit:
                break
    return {
        "question": question,
        "provenance": provenance,
        "literals": literals,
        "topic_tokens": tokens,
        "name_hits": name_hits,
        "table_hits": table_hits,
        "note": "命中来自这一份目录索引。",
    }


def link_id(tables: Path, record_id: str, provenance: dict, limit: int = 20) -> dict:
    tables = Path(tables)
    hits = []
    needle = str(record_id)
    for path in sorted(tables.rglob("*.json")):
        if path.name.startswith("_"):
            continue
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            continue
        data = payload.get("data") if isinstance(payload, dict) and "data" in payload else payload
        if not isinstance(data, dict):
            continue
        rel = path.relative_to(tables).as_posix()
        if needle in data:
            hits.append({**provenance, "table": rel, "id": needle, "relation": "primary_key", "path": str(path)})
        else:
            for key, row in data.items():
                if not isinstance(row, dict):
                    continue
                for field in ("class_id", "item_id", "reward_id", "cfg_id", "id"):
                    if str(row.get(field)) == needle:
                        hits.append({**provenance, "table": rel, "id": str(key), "field": field, "relation": "field", "path": str(path)})
                        break
                if len(hits) >= limit:
                    break
        if len(hits) >= limit:
            break
    return {"record_id": needle, "provenance": provenance, "hits": hits[:limit]}

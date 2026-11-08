"""Search exported tables and trace cross-table references without mixing channels or versions."""

from __future__ import annotations

import json
import re
from pathlib import Path

from xian_skills.config.model import normalize_path
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
    ("灵域", ("lingyu",)),
    ("领域", ("lingyu",)),
)
TOPIC_WORDS = {word for word, _tokens in TOPICS}

_SELF_ID_KEYS = ("class_id", "id", "cfg_id", "item_id", "reward_id", "skill_id")
_HIGH_REF_KEYS = {
    "id",
    "ids",
    "class_id",
    "item_id",
    "reward_id",
    "cfg_id",
    "skill_id",
    "buff_id",
    "effect_id",
    "monster_id",
    "npc_id",
    "task_id",
    "mission_id",
    "shop_id",
    "exchange_id",
    "suit_id",
    "group_id",
    "type_id",
    "pre_id",
    "next_id",
    "unlock_id",
    "target_id",
    "counter_id",
    "template_id",
    "model_id",
    "sound_id",
    "audio_id",
    "icon",
    "icon_id",
    "icons",
    "prestige_id",
    "jade_item_id",
    "active_reward",
}
_HIGH_REF_SUFFIXES = (
    "_id",
    "_ids",
    "_class_id",
    "_item_id",
    "_skill_id",
    "_reward_id",
    "_cfg_id",
    "_icon",
    "_icons",
    "id_list",
)
_CONTAINER_REF_KEYS = {
    "reward",
    "rewards",
    "award",
    "awards",
    "cost",
    "costs",
    "consume",
    "consumes",
    "need",
    "material",
    "materials",
    "item",
    "items",
    "drop",
    "drops",
    "gift",
    "gifts",
    "exchange_cost",
    "buy_price",
    "sell_price",
    "affix",
    "active_affix",
    "unlock_cost",
    "upgrade_cost",
    "levelup_cost",
}
_CONTAINER_REF_SUFFIXES = (
    "_reward",
    "_rewards",
    "_award",
    "_awards",
    "_cost",
    "_costs",
    "_consume",
    "_material",
    "_materials",
    "_item",
    "_items",
    "_drop",
    "_drops",
    "_affix",
)
_VALUE_ONLY_KEYS = {
    "count",
    "num",
    "amount",
    "qty",
    "number",
    "weight",
    "prob",
    "probability",
    "rate",
    "ratio",
    "percent",
    "level",
    "level_min",
    "level_max",
    "level_require",
    "min_level",
    "max_level",
    "rank",
    "exp",
    "score",
    "power",
    "hp",
    "max_hp",
    "mp",
    "max_mp",
    "attack",
    "atk",
    "defense",
    "def",
    "speed",
    "crit",
    "dodge",
    "hitrate",
    "endurance",
    "price",
    "gold",
    "silver",
    "coin",
    "time",
    "duration",
    "cd",
    "cooldown",
    "interval",
    "delay",
    "limit",
    "max",
    "min",
    "combinable",
    "stack",
    "capacity",
    "order",
    "sort",
    "priority",
    "index",
    "idx",
    "pos",
    "x",
    "y",
    "z",
    "width",
    "height",
    "scale",
    "size",
    "color",
    "alpha",
    "damage",
    "hurt",
    "heal",
    "value",
    "param",
}
_VALUE_ONLY_SUFFIXES = (
    "_count",
    "_num",
    "_amount",
    "_qty",
    "_weight",
    "_prob",
    "_rate",
    "_ratio",
    "_percent",
    "_level",
    "_min",
    "_max",
    "_limit",
    "_time",
    "_cd",
    "_duration",
    "_price",
    "_exp",
    "_score",
    "_damage",
    "_scale",
    "_size",
)
_SKIP_JSON_NAMES = {"catalog.json", "master_index.json", "function_index.json"}
_MAX_CONTAINER_SCAN = 10000


def build_catalog(tables: Path, dest: Path, provenance: dict) -> dict:
    tables = normalize_path(tables) or Path(tables)
    dest = normalize_path(dest) or Path(dest)
    if not tables.is_dir():
        raise XianError(f"导表目录不存在：{tables}")
    dest.mkdir(parents=True, exist_ok=True)
    table_rows = []
    names = []
    nonempty_count = runtime_count = empty_count = 0
    for path in sorted(tables.rglob("*.json")):
        if path.name.startswith("_") or path.name in _SKIP_JSON_NAMES:
            continue
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, UnicodeDecodeError, json.JSONDecodeError):
            continue
        data = payload.get("data") if isinstance(payload, dict) and "data" in payload else payload
        rel = path.relative_to(tables).as_posix()
        fields = []
        if isinstance(data, dict):
            row_iter = list(data.items())
            entries = len(data)
        elif isinstance(data, list):
            row_iter = [(str(idx), item) for idx, item in enumerate(data)]
            entries = len(data)
        else:
            row_iter = []
            entries = 0
        if row_iter:
            sample = next((value for _k, value in row_iter if isinstance(value, dict)), None)
            if sample:
                fields = [str(key) for key in list(sample.keys())[:40]]
            for key, row in row_iter:
                if not isinstance(row, dict):
                    continue
                rec_id = str(row.get("id", key)) if isinstance(data, list) else str(key)
                for field in NAME_FIELDS:
                    value = row.get(field)
                    if isinstance(value, str) and value.strip():
                        names.append({"table": rel, "id": rec_id, "field": field, "value": value})
        data_status = (payload.get("data_status") if isinstance(payload, dict) else None) or (
            "nonempty" if entries > 0 else "empty"
        )
        if data_status == "runtime_generated":
            runtime_count += 1
        elif entries > 0:
            nonempty_count += 1
        else:
            empty_count += 1
        row_meta = {
            "rel": rel,
            "entries": entries,
            "data_status": data_status,
            "fields": fields,
            "path": str(path),
        }
        if isinstance(payload, dict) and payload.get("part_pattern"):
            row_meta["part_pattern"] = payload["part_pattern"]
        if isinstance(payload, dict) and payload.get("runtime_hint"):
            row_meta["runtime_hint"] = payload["runtime_hint"]
        table_rows.append(row_meta)
    catalog = {
        "channel": provenance.get("channel"),
        "version": provenance.get("version"),
        "snapshot": provenance.get("snapshot"),
        "tables_dir": str(tables),
        "nonempty_tables": nonempty_count,
        "runtime_generated_tables": runtime_count,
        "empty_tables": empty_count,
        "tables": table_rows,
        "names": names,
    }
    (dest / "catalog.json").write_text(json.dumps(catalog, ensure_ascii=False), encoding="utf-8")
    return {
        "dir": str(dest),
        "tables": len(table_rows),
        "nonempty_tables": nonempty_count,
        "runtime_generated_tables": runtime_count,
        "empty_tables": empty_count,
        "names": len(names),
        "channel": catalog["channel"],
        "version": catalog["version"],
        "snapshot": catalog["snapshot"],
    }


def load_catalog(path: Path) -> dict:
    path = normalize_path(path) or Path(path)
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
            hit = {
                **provenance,
                "table": row["rel"],
                "entries": row["entries"],
                "data_status": row.get("data_status") or ("nonempty" if row.get("entries") else "empty"),
                "fields": row["fields"],
                "path": row["path"],
            }
            if row.get("part_pattern"):
                hit["part_pattern"] = row["part_pattern"]
            if row.get("runtime_hint"):
                hit["runtime_hint"] = row["runtime_hint"]
            table_hits.append(hit)
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


def _scalar_matches(value: object, needle_str: str, needle_int: int | None) -> bool:
    if isinstance(value, bool) or value is None:
        return False
    if isinstance(value, int):
        return needle_int is not None and value == needle_int
    if isinstance(value, float):
        return needle_int is not None and value.is_integer() and int(value) == needle_int
    if isinstance(value, str):
        return value.strip() == needle_str
    return False


def _format_field_path(path_tokens: list[tuple[str, str | int]]) -> str:
    if not path_tokens:
        return "$value"
    parts: list[str] = []
    for idx, (kind, token) in enumerate(path_tokens):
        if kind == "index":
            parts.append(f"[{token}]")
        else:
            key_text = str(token)
            if idx == 0:
                parts.append(key_text)
            else:
                parts.append(f".{key_text}")
    return "".join(parts)


def _is_high_ref_key(key_lower: str) -> bool:
    return key_lower in _HIGH_REF_KEYS or key_lower.endswith(_HIGH_REF_SUFFIXES)


def _is_container_ref_key(key_lower: str) -> bool:
    return key_lower in _CONTAINER_REF_KEYS or key_lower.endswith(_CONTAINER_REF_SUFFIXES)


def _is_value_only_key(key_lower: str) -> bool:
    return key_lower in _VALUE_ONLY_KEYS or key_lower.endswith(_VALUE_ONLY_SUFFIXES)


def _classify_match(
    table_rel: str,
    path_tokens: list[tuple[str, str | int]],
    parent_node: object,
    leaf_value: object,
    is_dict_key: bool = False,
) -> tuple[str, str]:
    key_tokens = [str(val).lower() for kind, val in path_tokens if kind == "key"]
    last_key = key_tokens[-1] if key_tokens else ""

    if is_dict_key:
        k_str = str(leaf_value).strip()
        if k_str.isdigit() and int(k_str) < 1000 and len(path_tokens) > 1:
            return "value_match", "low"
        if any(_is_high_ref_key(k) or _is_container_ref_key(k) for k in key_tokens[:-1]):
            return "semantic_reference", "high"
        return "semantic_reference", "medium"

    if path_tokens and path_tokens[-1][0] == "key" and _is_value_only_key(last_key):
        return "value_match", "low"

    # Tuple/pair like [item_id, count] or [count, "str_id"] inside a container
    if (
        path_tokens
        and path_tokens[-1][0] == "index"
        and isinstance(parent_node, list)
        and len(parent_node) in (2, 3)
        and all(not isinstance(item, (dict, list)) for item in parent_node)
    ):
        idx = int(path_tokens[-1][1])
        in_ref_container = any(_is_container_ref_key(k) or _is_high_ref_key(k) for k in key_tokens)
        if in_ref_container:
            first, second = parent_node[0], parent_node[1]
            if isinstance(first, (int, float)) and not isinstance(first, bool) and isinstance(second, str):
                return ("semantic_reference", "high") if idx == 1 else ("value_match", "low")
            return ("semantic_reference", "high") if idx == 0 else ("value_match", "low")

    if last_key and _is_high_ref_key(last_key):
        return "semantic_reference", "high"

    if any(_is_high_ref_key(k) for k in key_tokens[:-1]):
        if not last_key or last_key.isdigit() or not _is_value_only_key(last_key):
            return "semantic_reference", "high"

    if last_key == "data" and isinstance(parent_node, dict):
        sibling_keys = {str(k).lower() for k in parent_node.keys()}
        if sibling_keys & {"reward_type", "item_type", "amount", "weight", "count", "drop_type"} or "reward" in table_rel.lower():
            return "semantic_reference", "high"

    if any(_is_container_ref_key(k) for k in key_tokens):
        if not (last_key and _is_value_only_key(last_key)):
            return "semantic_reference", "medium"

    if not key_tokens and len(path_tokens) == 1 and path_tokens[0][0] == "index":
        table_lower = table_rel.lower()
        if any(tok in table_lower for tok in ("icon", "item", "reward", "skill", "id")) or isinstance(leaf_value, str):
            return "semantic_reference", "medium"

    return "value_match", "low"


_CONF_RANK = {"high": 3, "medium": 2, "low": 1}


def link_id(
    tables: Path,
    record_id: str | int,
    provenance: dict,
    limit: int = 50,
    mode: str = "all",
    max_depth: int = 16,
) -> dict:
    tables = normalize_path(tables) or Path(tables)
    if not tables.is_dir():
        raise XianError(f"导表目录不存在：{tables}")
    if mode not in ("all", "semantic"):
        raise XianError(f"不支持的关联模式：{mode}。可选：all、semantic")
    needle_str = str(record_id).strip()
    if not needle_str:
        raise XianError("关联查询需要非空 ID")
    needle_int = int(needle_str) if re.fullmatch(r"-?\d+", needle_str) else None

    channel = provenance.get("channel") or None
    version = provenance.get("version") or None
    snapshot = provenance.get("snapshot") or None
    prov_fields = {
        "channel": channel,
        "version": version,
        "snapshot": snapshot,
        "source_channel": channel,
        "source_version": version,
        "snapshot_id": snapshot,
    }

    all_hits: list[dict] = []
    truncated_depth = 0
    unreadable_files = 0

    def _walk(
        node: object,
        path_tokens: list[tuple[str, str | int]],
        depth: int,
        table_rel: str,
        rec_Matches: dict[str, dict],
    ) -> None:
        nonlocal truncated_depth
        if depth > max_depth:
            truncated_depth += 1
            return
        if isinstance(node, dict):
            for idx, (k, v) in enumerate(node.items()):
                if idx >= _MAX_CONTAINER_SCAN:
                    break
                k_str = str(k)
                child_tokens = [*path_tokens, ("key", k_str)]
                if k_str.strip() == needle_str:
                    fpath = _format_field_path(child_tokens)
                    mtype, conf = _classify_match(table_rel, child_tokens, node, k, is_dict_key=True)
                    top_field = str(child_tokens[0][1]) if child_tokens else k_str
                    rec_Matches[fpath] = {
                        "field": top_field,
                        "field_path": fpath,
                        "matched_value": k,
                        "relation": "field",
                        "match_type": mtype,
                        "reference_confidence": conf,
                    }
                if isinstance(v, (dict, list)):
                    _walk(v, child_tokens, depth + 1, table_rel, rec_Matches)
                elif _scalar_matches(v, needle_str, needle_int):
                    fpath = _format_field_path(child_tokens)
                    mtype, conf = _classify_match(table_rel, child_tokens, node, v, is_dict_key=False)
                    top_field = str(child_tokens[0][1]) if child_tokens else k_str
                    existing = rec_Matches.get(fpath)
                    if not existing or _CONF_RANK.get(conf, 0) >= _CONF_RANK.get(existing["reference_confidence"], 0):
                        rec_Matches[fpath] = {
                            "field": top_field,
                            "field_path": fpath,
                            "matched_value": v,
                            "relation": "field",
                            "match_type": mtype,
                            "reference_confidence": conf,
                        }
        elif isinstance(node, list):
            for idx, item in enumerate(node):
                if idx >= _MAX_CONTAINER_SCAN:
                    break
                child_tokens = [*path_tokens, ("index", idx)]
                if isinstance(item, (dict, list)):
                    _walk(item, child_tokens, depth + 1, table_rel, rec_Matches)
                elif _scalar_matches(item, needle_str, needle_int):
                    fpath = _format_field_path(child_tokens)
                    mtype, conf = _classify_match(table_rel, child_tokens, node, item, is_dict_key=False)
                    top_field = str(child_tokens[0][1]) if child_tokens and child_tokens[0][0] == "key" else f"[{idx}]"
                    rec_Matches[fpath] = {
                        "field": top_field,
                        "field_path": fpath,
                        "matched_value": item,
                        "relation": "field",
                        "match_type": mtype,
                        "reference_confidence": conf,
                    }
        elif _scalar_matches(node, needle_str, needle_int):
            fpath = _format_field_path(path_tokens)
            mtype, conf = _classify_match(table_rel, path_tokens, None, node, is_dict_key=False)
            rec_Matches[fpath] = {
                "field": fpath,
                "field_path": fpath,
                "matched_value": node,
                "relation": "field",
                "match_type": mtype,
                "reference_confidence": conf,
            }

    for path in sorted(tables.rglob("*.json")):
        if path.name.startswith("_") or path.name in _SKIP_JSON_NAMES:
            continue
        try:
            raw_text = path.read_text(encoding="utf-8")
        except (OSError, UnicodeDecodeError):
            unreadable_files += 1
            continue
        if needle_str not in raw_text and not (not needle_str.isascii() and "\\u" in raw_text):
            continue
        try:
            payload = json.loads(raw_text)
        except json.JSONDecodeError:
            unreadable_files += 1
            continue
        data = payload.get("data") if isinstance(payload, dict) and "data" in payload else payload
        if not isinstance(data, (dict, list)) or not data:
            continue
        rel = path.relative_to(tables).as_posix()
        if isinstance(data, dict):
            records_iter = [(str(k), k, v, str(k).strip() == needle_str) for k, v in data.items()]
        else:
            records_iter = [(str(idx), idx, v, False) for idx, v in enumerate(data)]

        for rec_key, raw_key, rec_val, pk_matched in records_iter:
            rec_matches: dict[str, dict] = {}
            _walk(rec_val, [], 1, rel, rec_matches)
            if pk_matched:
                folded = False
                for self_key in _SELF_ID_KEYS:
                    if self_key in rec_matches:
                        rec_matches[self_key]["relation"] = "primary_key"
                        rec_matches[self_key]["match_type"] = "semantic_reference"
                        rec_matches[self_key]["reference_confidence"] = "high"
                        folded = True
                        break
                if not folded:
                    rec_matches = {
                        "$key": {
                            "field": "$key",
                            "field_path": "$key",
                            "matched_value": raw_key,
                            "relation": "primary_key",
                            "match_type": "semantic_reference",
                            "reference_confidence": "high",
                        },
                        **rec_matches,
                    }
            for item in rec_matches.values():
                all_hits.append(
                    {
                        **prov_fields,
                        "table": rel,
                        "id": rec_key,
                        "record_key": rec_key,
                        "field": item["field"],
                        "field_path": item["field_path"],
                        "matched_value": item["matched_value"],
                        "relation": item["relation"],
                        "match_type": item["match_type"],
                        "reference_confidence": item["reference_confidence"],
                        "path": str(path),
                    }
                )

    semantic_hits = [hit for hit in all_hits if hit["match_type"] == "semantic_reference"]
    value_matches = [hit for hit in all_hits if hit["match_type"] == "value_match"]
    selected = semantic_hits if mode == "semantic" else (semantic_hits + value_matches)
    limited = selected[:limit] if limit and limit > 0 else selected
    return {
        "record_id": needle_str,
        "link_mode": mode,
        "provenance": provenance,
        "total_matches": len(all_hits),
        "semantic_count": len(semantic_hits),
        "value_match_count": len(value_matches),
        "tables_matched": len({hit["table"] for hit in selected}),
        "truncated_depth": truncated_depth,
        "unreadable_files": unreadable_files,
        "hits": limited,
        "semantic_hits": semantic_hits[:limit] if limit and limit > 0 else semantic_hits,
        "value_matches": value_matches[:limit] if limit and limit > 0 else value_matches,
        "note": (
            "semantic_reference 表示主键或具有明确 ID/图标/奖励/消耗语义的跨表引用；"
            "value_match 表示仅数值或字符串相等、尚未确认引用语义的候选关联。"
        ),
    }


def format_link_report(report: dict) -> str:
    prov = report.get("provenance") or {}
    lines = [
        f"跨表关联查询: {report.get('record_id')} (mode={report.get('link_mode', 'all')})",
        f"来源: channel={prov.get('channel') or '未指定'} version={prov.get('version') or '未指定'} snapshot={prov.get('snapshot') or '未指定'}",
        f"共发现 {report.get('total_matches', 0)} 处匹配（明确引用 {report.get('semantic_count', 0)}，候选值匹配 {report.get('value_match_count', 0)}），涉及 {report.get('tables_matched', 0)} 张表：",
        "",
        "[明确引用 semantic_reference]",
    ]
    sem = report.get("semantic_hits") or []
    if sem:
        for hit in sem:
            lines.append(
                f"  - 表 {hit['table']} | 记录 {hit['record_key']} | 字段路径 {hit['field_path']} | "
                f"匹配值 {json.dumps(hit['matched_value'], ensure_ascii=False)} (confidence={hit['reference_confidence']}, {hit['relation']})"
            )
    else:
        lines.append("  - 无")
    if report.get("link_mode", "all") == "all":
        lines.extend(["", "[候选关联 value_match（仅值相等，需结合上下文确认是否为真实引用）]"])
        vals = report.get("value_matches") or []
        if vals:
            for hit in vals:
                lines.append(
                    f"  - [候选关联] 表 {hit['table']} | 记录 {hit['record_key']} | 字段路径 {hit['field_path']} | "
                    f"匹配值 {json.dumps(hit['matched_value'], ensure_ascii=False)} (confidence={hit['reference_confidence']})"
                )
        else:
            lines.append("  - 无")
    return "\n".join(lines)

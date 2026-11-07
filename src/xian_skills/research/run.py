"""Run one research question against a catalog and leave the snapshots untouched."""

from __future__ import annotations

import json
from pathlib import Path

from xian_skills.query.ask import ask, load_catalog
from xian_skills.research.plan import SECTIONS, plan
from xian_skills.updates.records import same_channel_history
from xian_skills.version import __version__


def run_question(question: str, catalog_path: Path, out_dir: Path, history: list[dict] | None = None) -> dict:
    catalog = load_catalog(catalog_path)
    asked = ask(catalog, question)
    planned = plan(question)
    history_note = same_channel_history(history or [])
    facts = []
    inferences = []
    hypotheses = []
    unknown = [
        "客户端配置里的数值还不是服务器最终结算。",
        history_note["reason"] or "同一渠道有不止一个完整版本，可以再做历史对比。",
    ]
    if asked["name_hits"]:
        for hit in asked["name_hits"][:8]:
            facts.append(
                {
                    "statement": f"{hit['table']} 的记录 {hit['id']} 在字段 {hit['field']} 上包含查询词。",
                    "value": hit["value"],
                    "channel": hit.get("channel"),
                    "version": hit.get("version"),
                    "snapshot": hit.get("snapshot"),
                    "table": hit["table"],
                    "id": hit["id"],
                }
            )
    else:
        hypotheses.append("名称索引里没有直接命中。可能是这批表还没导出，或者问题里的名字不在 name 字段。")
    if asked["table_hits"]:
        inferences.append(
            {
                "statement": "这些问题词出现在下列表名或字段名里，值得继续打开原表核对。",
                "tables": [row["table"] for row in asked["table_hits"][:12]],
            }
        )
    unknown.append("没有战斗样本或服务器规则时，不能把配置关联写成机制已经验证。")
    report = {
        "tool_version": __version__,
        "question": question,
        "provenance": asked["provenance"],
        "plan": planned,
        "已确认事实": facts,
        "有证据支持的推断": inferences,
        "待验证假设": hypotheses,
        "当前无法判断": [item for item in unknown if item],
        "sections": list(SECTIONS),
    }
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / "report.json").write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    lines = [f"# {question}", "", f"数据：{asked['provenance']}", ""]
    for title in SECTIONS:
        lines.append(f"## {title}")
        lines.append("")
        rows = report[title]
        if not rows:
            lines.append("- 无")
        for row in rows:
            if isinstance(row, dict):
                lines.append(f"- {row.get('statement') or row}")
            else:
                lines.append(f"- {row}")
        lines.append("")
    (out_dir / "report.md").write_text("\n".join(lines), encoding="utf-8")
    return {"out": str(out_dir), "facts": len(facts), "tables": len(asked["table_hits"]), "names": len(asked["name_hits"]), "provenance": asked["provenance"]}

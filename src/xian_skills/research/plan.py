"""Research plans and a scratch workspace that does not touch raw snapshots."""

from __future__ import annotations

import json
import re
from pathlib import Path

from xian_skills.version import __version__

SECTIONS = ("已确认事实", "有证据支持的推断", "待验证假设", "当前无法判断")


def plan(question: str) -> dict:
    text = question or ""
    lowered = text.lower()
    steps = [
        {"command": "xian status", "why": "先看环境、客户端和已有数据，不要假设功能已经验证。"},
    ]
    tags = []
    if any(word in text for word in ("秘境", "会抗", "怪物气血", "诱妖")):
        tags.append("mijing")
        steps.append({"command": "xian research mijing --jsonl <你的cap.jsonl>", "why": "用这场授权记录反推会心和伤害样本。"})
    if any(word in text for word in ("命中", "会心", "破防", "格挡", "PVP", "pvp", "切磋", "神通")):
        tags.append("pvp")
        steps.append({"command": "xian research pvp --hitrate <数值> --dodge <数值>", "why": "用客户端系数做可复核的换算，并标明它还不是服务器结算。"})
        steps.append({"command": "xian query --kind table --q calc", "why": "在已导出的配置里核对系数来源。"})
        steps.append({"command": "xian search --root <lua目录> --q <神通名>", "why": "找客户端里能读到的计算和配置，不把查不到的部分说成服务器规则。"})
    if any(word in text for word in ("活动", "奖励", "兑换", "月活动", "消耗")):
        tags.append("events")
        steps.append({"command": "xian events analyze --tables <导表目录>", "why": "从配置里找活动、奖励和消耗，并列出计算假设。"})
    if any(word in text for word in ("更新", "版本", "差异", "证道")):
        tags.append("updates")
        steps.append({"command": "xian updates report --left <旧> --right <新> --output <报告.md>", "why": "对比两个快照或两套导表。"})
    if any(word in lowered for word in ("抓包", "协议", "上行")):
        tags.append("capture")
        steps.append({"command": "xian capture start --session <名字> --yes", "why": "只有在你确认之后才采集你自己的会话。"})
    if not tags:
        tags.append("explore")
        steps.append({"command": "xian query --kind table --q <关键词>", "why": "先在配置索引里定位名词，再决定要不要新数据。"})
    steps.append(
        {
            "command": "xian research init-script --name <题目>",
            "why": "需要临时计算时，把脚本放在研究目录，不要改原始快照。",
        }
    )
    return {
        "question": text,
        "tags": tags,
        "steps": steps,
        "must_separate": list(SECTIONS),
        "unknown_until_proven": [
            "客户端没有出现的随机过程、个人条件限制和服务器最终改写",
        ],
    }


def init_script(root: Path, name: str) -> dict:
    safe = re.sub(r"[^0-9A-Za-z_\-\u4e00-\u9fff]", "_", name).strip("_") or "study"
    dest = Path(root) / safe
    dest.mkdir(parents=True, exist_ok=True)
    (dest / "inputs.json").write_text(
        json.dumps({"tool_version": __version__, "inputs": [], "note": "只记录路径和版本，不复制账号数据。"}, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    (dest / "study.py").write_text(
        "# 临时研究脚本。只读输入，结果写到本目录的 outputs/。\n"
        "import json\nfrom pathlib import Path\n\n"
        "ROOT = Path(__file__).resolve().parent\n"
        "inputs = json.loads((ROOT / 'inputs.json').read_text(encoding='utf-8'))\n"
        "(ROOT / 'outputs').mkdir(exist_ok=True)\n",
        encoding="utf-8",
    )
    (dest / "RESULT.md").write_text(
        f"# {safe}\n\n"
        "## 已确认事实\n\n-\n\n"
        "## 有证据支持的推断\n\n-\n\n"
        "## 待验证假设\n\n-\n\n"
        "## 当前无法判断\n\n-\n\n"
        "## 复现\n\n- 输入版本：\n- 命令：\n",
        encoding="utf-8",
    )
    (dest / "outputs").mkdir(exist_ok=True)
    return {"dir": str(dest)}

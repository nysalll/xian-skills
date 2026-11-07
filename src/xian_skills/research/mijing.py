"""Invert monster survival stats from the user's own combat jsonl.

The default crit curve matches the client calc constants used by the PVP
helper. A fit on too few hits stays a hypothesis.
"""

from __future__ import annotations

import json
import math
from collections import defaultdict
from pathlib import Path

P = 0.8
Q = 0.26
CRIT_LO = 0.01
CRIT_HI = 0.50


def wilson(successes: int, total: int, z: float = 1.96):
    if total <= 0:
        return None, None, None
    ratio = successes / total
    den = 1 + z * z / total
    center = (ratio + z * z / (2 * total)) / den
    half = z * math.sqrt(ratio * (1 - ratio) / total + z * z / (4 * total * total)) / den
    return ratio, max(0.0, center - half), min(1.0, center + half)


def invert_resist(crit_value, rate):
    if crit_value is None or crit_value <= 0 or rate is None:
        return None
    if rate <= CRIT_LO + 1e-9 or rate >= CRIT_HI - 1e-9:
        return None
    return Q * crit_value * (1.0 - rate) / ((1.0 - P) + P * rate)


def resist_cap(crit_value):
    if not crit_value:
        return None
    return Q * crit_value / (2.0 - P)


def invert_attack(damage, defense):
    if not damage or not defense or damage <= 0 or defense <= 0:
        return None
    return (damage + math.sqrt(damage * damage + 4.0 * damage * defense)) / 2.0


def _median(values):
    if not values:
        return None
    ordered = sorted(values)
    return ordered[len(ordered) // 2]


def summarize_jsonl(path: Path, me: str | None = None) -> dict:
    path = Path(path)
    monsters = {}
    hits = []
    player_crit = []
    with path.open(encoding="utf-8") as handle:
        for line in handle:
            if not line.strip():
                continue
            record = json.loads(line)
            message = record.get("msg")
            if not isinstance(message, list) or not message:
                continue
            name = message[0]
            if name == "appear" and len(message) > 1:
                body = message[1]
                row = None
                if isinstance(body, dict):
                    row = body
                elif isinstance(body, list):
                    row = next((item for item in body if isinstance(item, dict) and "rid" in item), None)
                if row and row.get("type") == "monster":
                    monsters[row.get("rid")] = {"name": row.get("name"), "keys": sorted(row.keys())}
            elif name == "attrib_update" and isinstance(message[1], list) and len(message[1]) >= 4:
                payload = message[1]
                if payload[1] == "crit_chance":
                    player_crit.append(payload[3])
            elif name == "skill_hit" and isinstance(message[1], list) and len(message[1]) >= 8:
                payload = message[1]
                spec = payload[7]
                crit = bool(spec[0]) if isinstance(spec, list) and spec else False
                hits.append({"atk": payload[0], "tgt": payload[3], "dmg": payload[4] or 0, "crit": crit})
    if me is None:
        counts = defaultdict(int)
        for hit in hits:
            counts[str(hit["atk"])] += 1
        me = max(counts, key=counts.get) if counts else None
    outgoing = [hit for hit in hits if me is None or str(hit["atk"]) == str(me)]
    successes = sum(1 for hit in outgoing if hit["crit"])
    rate, low, high = wilson(successes, len(outgoing))
    crit_value = _median(player_crit)
    resist = invert_resist(crit_value, rate)
    damages = [hit["dmg"] for hit in outgoing if hit["dmg"]]
    return {
        "evidence": "capture_sample",
        "limitation": "样本只说明这场记录。客户端系数不等于服务器结算；样本少、会心贴顶或看不到防御时，攻击反推保持为假设。",
        "player": me,
        "monsters": len(monsters),
        "monster_sample": list(monsters.values())[:8],
        "hits": len(outgoing),
        "crits": successes,
        "crit_rate": rate,
        "crit_rate_ci": [low, high],
        "player_crit_median": crit_value,
        "resist_estimate": resist,
        "resist_cap": resist_cap(crit_value),
        "damage_median": _median(damages),
        "hypothesis": resist is None,
    }

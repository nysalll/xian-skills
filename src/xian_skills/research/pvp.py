"""PVP rates from client calc constants.

These coefficients describe formulas previously read from client config.
They are not proof of the server's final damage settlement.
"""

from __future__ import annotations

import json
from pathlib import Path

HIT_M, HIT_N = 0.9, 0.15
HIT_RANGE = (25.0, 99.0)
CRIT_P, CRIT_Q = 0.8, 0.26
CRIT_RANGE = (1.0, 50.0)
CRIT_DMG_BASE = 150.0
DIM_RATE, DIM_LIMIT = 0.1, 50.0
EX_PROB, EX_RATE, EX_LIMIT = 30.0, 0.1, 40.0
ATTACK_RANDOM = (95, 105)
HEARTBEAT = 1.4
ENDURANCE_FACTOR, ENDURANCE_THRESHOLD = 0.1, 100.0
ATTEN = {0: 1.0, 1: 1.0, 2: 1.0, 3: 0.95, 4: 0.90, 5: 0.85}
ATTEN_DEFAULT = 0.80

EVIDENCE = "client_config_defaults"


def clamp(value, low, high):
    return max(low, min(high, value))


def hit_rate(hitrate, dodge, hit_m=HIT_M, hit_n=HIT_N, hit_range=HIT_RANGE):
    if hitrate <= 0 or dodge <= 0:
        return None
    return clamp(hitrate / (hitrate * hit_m + dodge * hit_n) * 100, *hit_range)


def crit_rate(crit, crit_resist, crit_p=CRIT_P, crit_q=CRIT_Q, crit_range=CRIT_RANGE):
    if crit <= 0 or crit_resist <= 0:
        return None
    return clamp(100 - crit_resist / (crit_resist * crit_p + crit * crit_q) * 100, *crit_range)


def pierce(my_dim, op_dim, rate=DIM_RATE, limit=DIM_LIMIT):
    return clamp(max(0.0, my_dim - op_dim) * rate, 0.0, limit)


def block(my_ex, op_ex, rate=EX_RATE, prob=EX_PROB, limit=EX_LIMIT):
    value = clamp(max(0.0, my_ex - op_ex) * rate, 0.0, limit)
    return value, value * prob / 100.0


def skill_atten(user_rank, skill_rank):
    delta = min(13, max(0, user_rank - skill_rank))
    return ATTEN.get(delta, ATTEN_DEFAULT)


def endurance_reduce(endurance, layers):
    return min(100.0, endurance * max(1, layers) * ENDURANCE_FACTOR)


def _setting(node):
    if isinstance(node, dict) and "value" in node:
        return node["value"]
    return node


def coefs_from_table(path: Path) -> dict:
    payload = json.loads(Path(path).read_text(encoding="utf-8"))
    data = payload.get("data") if isinstance(payload, dict) else None
    if not isinstance(data, dict):
        return {"loaded": False, "evidence": EVIDENCE}
    coefs = {}
    mapping = {
        "hp_hitrate_coefficient_m": "hit_m",
        "hp_hitrate_coefficient_n": "hit_n",
        "hitrate_range": "hit_range",
        "crit_coefficient_p": "crit_p",
        "crit_coefficient_q": "crit_q",
        "crit_range": "crit_range",
        "crit_damage_base": "crit_damage_base",
    }
    for source, target in mapping.items():
        if source in data:
            coefs[target] = _setting(data[source])
    dim = _setting(data.get("hp_defense_dim_coefficient"))
    ex = _setting(data.get("hp_defense_ex_coefficient"))
    if isinstance(dim, dict):
        coefs["dim_rate"] = dim.get("rate", DIM_RATE)
        coefs["dim_limit"] = dim.get("limit", DIM_LIMIT)
    if isinstance(ex, dict):
        coefs["ex_rate"] = ex.get("rate", EX_RATE)
        coefs["ex_prob"] = ex.get("prob", EX_PROB)
        coefs["ex_limit"] = ex.get("limit", EX_LIMIT)
    return {"loaded": bool(coefs), "path": str(path), "coefs": coefs, "evidence": "local_table" if coefs else EVIDENCE}


def evaluate(values: dict, coefs: dict | None = None) -> dict:
    coefs = coefs or {}
    hit = hit_rate(
        values.get("hitrate") or 0,
        values.get("dodge") or 0,
        coefs.get("hit_m", HIT_M),
        coefs.get("hit_n", HIT_N),
        tuple(coefs.get("hit_range", HIT_RANGE)),
    )
    crit = crit_rate(
        values.get("crit") or 0,
        values.get("crit_resist") or 0,
        coefs.get("crit_p", CRIT_P),
        coefs.get("crit_q", CRIT_Q),
        tuple(coefs.get("crit_range", CRIT_RANGE)),
    )
    pierced = pierce(
        values.get("my_dim") or 0,
        values.get("op_dim") or 0,
        coefs.get("dim_rate", DIM_RATE),
        coefs.get("dim_limit", DIM_LIMIT),
    )
    blocked, blocked_expected = block(
        values.get("my_ex") or 0,
        values.get("op_ex") or 0,
        coefs.get("ex_rate", EX_RATE),
        coefs.get("ex_prob", EX_PROB),
        coefs.get("ex_limit", EX_LIMIT),
    )
    crit_damage = values.get("crit_damage", CRIT_DMG_BASE)
    effective_crit = max(100.0, crit_damage - (values.get("op_crit_defense") or 0))
    result = {
        "evidence": "local_table" if coefs else EVIDENCE,
        "limitation": "这是客户端配置里的换算，不是服务器最终结算。要用你自己授权采集的战斗记录核对。",
        "hit_rate_percent": hit,
        "crit_rate_percent": crit,
        "pierce_percent": pierced,
        "block_percent": blocked,
        "block_expected_percent": blocked_expected,
        "effective_crit_damage_percent": effective_crit,
        "attack_random_percent": list(ATTACK_RANDOM),
        "heartbeat_seconds": HEARTBEAT,
    }
    if values.get("user_rank") and values.get("skill_rank"):
        result["skill_attenuation"] = skill_atten(int(values["user_rank"]), int(values["skill_rank"]))
    if values.get("as_base") is not None:
        scale = float(values["as_base"]) + (int(values.get("skill_level") or 1) - 1) * float(values.get("as_grow") or 0)
        result["skill_scale"] = scale
    if values.get("endurance"):
        result["endurance_reduce_percent"] = endurance_reduce(float(values["endurance"]), int(values.get("layers") or 1))
    return result


def load_coef_note(path: Path | None) -> dict:
    if not path or not Path(path).is_file():
        return {"loaded": False, "evidence": EVIDENCE}
    payload = json.loads(Path(path).read_text(encoding="utf-8"))
    text = json.dumps(payload, ensure_ascii=False)
    keys = [
        "hp_hitrate_coefficient_m",
        "crit_coefficient_p",
        "crit_coefficient_q",
        "crit_range",
        "hitrate_range",
    ]
    present = [key for key in keys if key in text]
    return {"loaded": True, "path": str(path), "present_keys": present, "evidence": "local_table" if present else EVIDENCE}

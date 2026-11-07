"""Feature states. A passing import is not a verified feature."""

from __future__ import annotations

import json
from pathlib import Path

FEATURES = [
    {"id": "environment", "title": "环境检测与初始化", "needs": []},
    {"id": "client_version", "title": "客户端版本识别", "needs": ["adb"]},
    {"id": "client_pull", "title": "客户端完整文件提取", "needs": ["adb"]},
    {"id": "client_sync", "title": "增量更新与版本对比", "needs": ["adb"]},
    {"id": "lua_decode", "title": "Lua 解密", "needs": ["UnityPy"]},
    {"id": "lua_decompile", "title": "Lua 反编译", "needs": ["decompiler"]},
    {"id": "lua_tables", "title": "游戏配置导表", "needs": []},
    {"id": "query", "title": "自然语言问题背后的数据查询", "needs": []},
    {"id": "channel_diff", "title": "正式服与证道服配置差异", "needs": []},
    {"id": "capture", "title": "网络流量录制", "needs": ["adb"]},
    {"id": "protocol", "title": "网络协议与消息解析", "needs": ["msgpack"]},
    {"id": "uplink", "title": "上行消息解码", "needs": ["msgpack", "Crypto"]},
    {"id": "logs", "title": "日志查询与统计", "needs": []},
    {"id": "assets_image", "title": "图片和模型资源导出", "needs": ["UnityPy"]},
    {"id": "assets_media", "title": "音频和视频资源导出", "needs": []},
    {"id": "mijing", "title": "秘境数据反推", "needs": []},
    {"id": "pvp", "title": "PVP 与其他机制分析", "needs": []},
    {"id": "runtime", "title": "运行时动态探测", "needs": ["adb"]},
    {"id": "update_report", "title": "客户端版本更新报告", "needs": []},
    {"id": "events", "title": "活动配置、奖励和资源消耗分析", "needs": []},
]


def cap_path(data_dir: Path) -> Path:
    return Path(data_dir) / "capabilities.json"


def load_caps(data_dir: Path) -> dict:
    path = cap_path(data_dir)
    if not path.is_file():
        return {}
    return json.loads(path.read_text(encoding="utf-8"))


def save_cap(data_dir: Path, feature: str, state: str, evidence: str) -> None:
    path = cap_path(data_dir)
    path.parent.mkdir(parents=True, exist_ok=True)
    data = load_caps(data_dir)
    data[feature] = {"state": state, "evidence": evidence}
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def _dep_ok(need: str, doctor: dict) -> bool:
    if need == "adb":
        return bool((doctor.get("adb") or {}).get("ok"))
    if need == "decompiler":
        return any(row["name"] == "luajit-decompiler" and row["ok"] for row in doctor.get("external_tools") or [])
    modules = {row["name"]: row["ok"] for row in doctor.get("modules") or []}
    return bool(modules.get(need))


def effective_state(feature: dict, doctor: dict, stored: dict) -> str:
    missing = [need for need in feature["needs"] if not _dep_ok(need, doctor)]
    state = (stored.get(feature["id"]) or {}).get("state") or "unverified"
    if missing and state != "unsupported":
        return "missing_deps"
    if state in {"basic_tested", "verified", "failed", "unsupported", "ready"}:
        return state
    if not missing:
        return "ready"
    return "unverified"


def examples_for(states: dict, clients: list[dict] | None = None) -> list[str]:
    clients = clients or []
    installed = [row for row in clients if row.get("installed")]
    prompts = ["帮我检查这台电脑和 MuMu，告诉我 xian-skills 现在哪些功能验证过、哪些还不能用。"]
    if any(row.get("version") for row in installed):
        prompts.append("读取当前已安装的一念逍遥客户端版本，区分正式服和证道服。")
    else:
        prompts.append("如果模拟器里已经装了游戏，帮我识别正式服或证道服；没装的渠道不要当成失败。")
    prompts.extend(
        [
            "从我导出的配置里查一张表，并说明这是客户端配置，不是服务器结算。",
            "对比两个版本的配置，生成更新报告，列出新增、删除和变化。",
            "分析活动配置里的奖励和兑换消耗，标出哪些数量是配置直接给出的，哪些还要服务器数据。",
            "用客户端系数估算一组命中、会心、破防，并写明哪些结论还没有战斗样本。",
        ]
    )
    if states.get("capture") == "verified":
        prompts.append("开始录我自己的这一场，结束后统计消息并解码上行。")
    return prompts


def build_status(doctor: dict, data_dir: Path, clients: list[dict] | None = None) -> dict:
    stored = load_caps(data_dir) if data_dir else {}
    rows = []
    for feature in FEATURES:
        state = effective_state(feature, doctor, stored)
        evidence = (stored.get(feature["id"]) or {}).get("evidence") or ""
        rows.append({"id": feature["id"], "title": feature["title"], "state": state, "evidence": evidence})
    states = {row["id"]: row["state"] for row in rows}
    return {
        "tool_version": doctor.get("tool_version"),
        "data_dir": str(data_dir),
        "online_devices": doctor.get("online_devices") or [],
        "clients": clients or [],
        "features": rows,
        "examples": examples_for(states, clients),
        "legend": {
            "not_installed": "未安装",
            "missing_deps": "缺少依赖",
            "ready": "环境已准备",
            "basic_tested": "已通过基础测试",
            "verified": "已通过实际功能验证",
            "failed": "验证失败",
            "unsupported": "当前环境不支持",
            "unverified": "尚未验证",
        },
    }


def format_status(report: dict) -> str:
    lines = [f"xian-skills {report.get('tool_version')}", f"数据目录 {report.get('data_dir')}", ""]
    warehouse = report.get("warehouse") or {}
    if warehouse:
        if warehouse.get("inside_project_tree"):
            lines.append("这份数据目前在项目目录里。仓库被删掉时，它会一起消失。")
        lines.append(f"用户数据目录 {warehouse.get('user_store')}")
        for row in warehouse.get("channels") or []:
            latest = row.get("latest_complete")
            if latest:
                lines.append(f"已提取 {row['channel']} {latest['version']}，{latest['files']} 个文件，快照 {latest['id']}")
            else:
                lines.append(f"{row['channel']} 还没有完整快照")
    devices = report.get("online_devices") or []
    lines.append("在线设备：" + ("、".join(devices) if devices else "无"))
    if report.get("clients"):
        lines.append("客户端：")
        for client in report["clients"]:
            version = (client.get("version") or {}).get("current") or "未知"
            flag = "已安装" if client.get("installed") else "未安装"
            lines.append(f"  {client.get('label')} {flag} {version}")
    lines.append("")
    lines.append("功能：")
    labels = report["legend"]
    for row in report["features"]:
        lines.append(f"  [{labels.get(row['state'], row['state'])}] {row['title']}")
        if row.get("evidence"):
            lines.append(f"    {row['evidence']}")
    if report.get("needs_authorization"):
        lines.append("")
        lines.append("需要你另外同意的操作：")
        for item in report["needs_authorization"]:
            lines.append(f"  - {item}")
    lines.append("")
    lines.append("可以直接这样问：")
    for item in report["examples"]:
        lines.append(f"  - {item}")
    return "\n".join(lines)

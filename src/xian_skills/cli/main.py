"""Unified CLI. Skills tell an agent which command to run; this module does the work."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from xian_skills.config.model import home_dir, load_config, normalize_path, save_config
from xian_skills.errors import EnvError, NeedConfirm, XianError
from xian_skills.version import __version__


def _p(raw: str | Path) -> Path:
    return normalize_path(raw) or Path(raw)


def _print(payload, as_json: bool, text: str | None = None) -> None:
    if as_json or text is None:
        print(json.dumps(payload, ensure_ascii=False, indent=2, default=str))
    else:
        print(text)


def _cfg(args):
    path = _p(args.config) if getattr(args, "config", "") else None
    return load_config(path)


def _warehouse(cfg):
    from xian_skills.storage.warehouse import Warehouse

    warehouse = Warehouse(cfg.data_dir)
    warehouse.ensure()
    return warehouse


def _adb(cfg, device: str = "", replace: bool = False):
    from xian_skills.device.adb import Adb
    from xian_skills.device.select import select_adb

    report = select_adb(cfg.data.get("adb_path") or "", auto_connect=bool(cfg.data.get("auto_connect", True)), replace=replace)
    exe = report.get("adb")
    if not exe:
        raise EnvError("没有找到 adb。安装 Platform-Tools，或在配置里写 adb_path。", payload=report)
    if report.get("adb") and not cfg.data.get("adb_path"):
        cfg.data["adb_path"] = exe
        save_config(cfg)
    serial = device or cfg.data.get("device") or ""
    online = report.get("online") or []
    if serial and serial in (report.get("offline") or []):
        raise EnvError(report.get("diagnosis") or f"{serial} 处于 offline。", payload=report)
    if not serial:
        if len(online) == 1:
            serial = online[0]
        elif not online:
            raise EnvError(report.get("diagnosis") or "没有在线设备。先启动模拟器，或用 --device 指定。", payload=report)
        else:
            raise NeedConfirm("有多台在线设备，请用 --device 指定。", payload={"devices": online})
    return Adb(exe, serial)


def _clients(cfg, adb):
    from xian_skills.client.sync import discover_client

    return discover_client(adb, cfg.data.get("channels") or {})


def _write_launcher() -> None:
    exe = Path(sys.executable).with_name("xian.exe")
    if not exe.is_file():
        alt = Path(sys.executable).parent / "Scripts" / "xian.exe"
        if alt.is_file():
            exe = alt
    home = home_dir()
    bin_dir = home / "bin"
    bin_dir.mkdir(parents=True, exist_ok=True)
    if exe.is_file():
        (home / "xian-launcher.txt").write_text(str(exe) + "\n", encoding="utf-8")
    bundled = Path(__file__).resolve().parents[3] / "installers" / "windows" / "xian.cmd"
    if bundled.is_file():
        (bin_dir / "xian.cmd").write_bytes(bundled.read_bytes())
    target_posix = (exe if exe.is_file() else Path(sys.executable)).resolve().as_posix()
    if exe.is_file():
        (bin_dir / "xian").write_text(f'#!/usr/bin/env sh\nexec "{target_posix}" "$@"\n', encoding="utf-8")
        (bin_dir / "xian.ps1").write_text(f'& "{exe.resolve()}" @args\r\nexit $LASTEXITCODE\r\n', encoding="utf-8")
    else:
        (bin_dir / "xian").write_text(f'#!/usr/bin/env sh\nexec "{target_posix}" -m xian_skills "$@"\n', encoding="utf-8")
        (bin_dir / "xian.ps1").write_text(f'& "{Path(sys.executable).resolve()}" -m xian_skills @args\r\nexit $LASTEXITCODE\r\n', encoding="utf-8")


def cmd_tools_decompiler(args):
    from xian_skills.tools.decompiler import install, status

    cfg = _cfg(args)
    payload = install(cfg, yes=args.yes) if args.install else status(cfg.data.get("decompiler_path") or "")
    _print(payload, args.json)
    return 0


def cmd_doctor(args):
    from xian_skills.environment.doctor import doctor, format_doctor

    report = doctor(_cfg(args), probe_devices=not args.no_device)
    _print(report, args.json, format_doctor(report))
    return 0 if report["python"]["ok"] else 2


def cmd_init(args):
    cfg = _cfg(args)
    if args.data_dir:
        cfg.data["data_dir"] = args.data_dir
    if args.adb:
        cfg.data["adb_path"] = args.adb
    if args.device:
        cfg.data["device"] = args.device
    save_config(cfg)
    _write_launcher()
    warehouse = _warehouse(cfg)
    deps = None
    if args.yes:
        if sys.prefix == getattr(sys, "base_prefix", sys.prefix):
            raise XianError("当前不是虚拟环境。请用 installers/windows/install.ps1 创建 .venv，再安装依赖。", code=2)
        import subprocess

        proc = subprocess.run(
            [sys.executable, "-m", "pip", "install", "msgpack", "pycryptodome", "UnityPy"],
            capture_output=True,
            text=True,
            errors="replace",
        )
        deps = {"code": proc.returncode, "tail": (proc.stdout or proc.stderr or "")[-500:]}
        if proc.returncode != 0:
            raise XianError("依赖安装失败", code=3, payload=deps)
    payload = {"config": str(cfg.path), "data_dir": str(warehouse.root), "deps": deps}
    _print(payload, args.json)
    return 0


def cmd_status(args):
    from xian_skills.diagnostics.status import build_status, format_status
    from xian_skills.environment.doctor import doctor

    cfg = _cfg(args)
    report = doctor(cfg, probe_devices=not args.no_device)
    clients = []
    if report.get("online_devices") and not args.no_device:
        try:
            serial = args.device or cfg.data.get("device") or (report["online_devices"][0] if len(report["online_devices"]) == 1 else "")
            if serial:
                from xian_skills.device.adb import Adb

                clients = _clients(cfg, Adb(report["adb"]["selected"], serial)).get("clients") or []
        except XianError:
            clients = []
    warehouse = _warehouse(cfg)
    status = build_status(report, cfg.data_dir, clients)
    from xian_skills.diagnostics.status import gate_states

    decompiler_ok = bool((report.get("decompiler") or {}).get("verified_hash") or (report.get("decompiler") or {}).get("usable"))
    has_snapshot = any(
        snap.get("complete")
        for channel in ("official", "zhengdao")
        for snap in warehouse.list_snapshots(channel)
    )
    status["features"] = gate_states(status["features"], decompiler_ok=decompiler_ok, has_snapshot=has_snapshot)
    from xian_skills.storage.warehouse import latest_complete

    extracted = []
    for channel in ("official", "zhengdao"):
        latest = latest_complete(warehouse, channel)
        snaps = warehouse.list_snapshots(channel)
        extracted.append(
            {
                "channel": channel,
                "snapshots": len(snaps),
                "complete_count": sum(1 for snap in snaps if snap.get("complete")),
                "latest_complete": None
                if latest is None
                else {"id": latest["id"], "version": latest.get("version"), "files": len(latest.get("files") or [])},
            }
        )
    data_path = Path(cfg.data_dir).resolve()
    status["warehouse"] = {
        "data_dir": str(data_path),
        "user_store": str(Path.home() / ".xian-skills" / "data"),
        "inside_project_tree": "xian-skills" in data_path.parts,
        "channels": extracted,
    }
    missing_ffmpeg = not any(row["name"] == "ffmpeg" and row["ok"] for row in report.get("external_tools") or [])
    status["needs_authorization"] = [
        "抓包会执行 adb root 并启动 tcpdump，必须单独同意。",
        "运行时探测会附加进程，必须单独同意。",
    ]
    if missing_ffmpeg:
        status["needs_authorization"].append("本机没有 ffmpeg。把 IVF 转成 mp4 需要先安装它，安装前要确认来源。")
    _print(status, args.json, format_status(status))
    return 0


def cmd_verify(args):
    from xian_skills.diagnostics.status import save_cap
    from xian_skills.diagnostics.verify import record_suite, run_suite

    cfg = _cfg(args)
    _warehouse(cfg)
    result = record_suite(cfg.data_dir, run_suite())
    device = None
    if args.device_check:
        try:
            adb = _adb(cfg, args.device)
            found = _clients(cfg, adb)
            device = found
            verified = []
            for client in found.get("clients") or []:
                if client.get("installed") and (client.get("version") or {}).get("current"):
                    verified.append(f"{client['channel']} {client['version']['current']}")
            if verified:
                save_cap(cfg.data_dir, "client_version", "verified", "; ".join(verified) + f" on {adb.serial}")
            if not verified:
                installed = [row["channel"] for row in (found.get("clients") or []) if row.get("installed")]
                if installed:
                    result["device_note"] = "客户端已安装，但没有读到 version.txt。"
                    save_cap(cfg.data_dir, "client_version", "failed", result["device_note"])
                else:
                    result["device_note"] = "设备在线，但没有安装已配置的游戏包。"
                    save_cap(cfg.data_dir, "client_version", "ready", result["device_note"])
        except (XianError, EnvError, NeedConfirm) as exc:
            device = {"error": str(exc)}
            save_cap(cfg.data_dir, "client_version", "failed", str(exc))
    result["device"] = device
    _print(result, args.json)
    return 0 if result.get("ok") else 1


def cmd_client_discover(args):
    cfg = _cfg(args)
    adb = _adb(cfg, args.device)
    payload = _clients(cfg, adb)
    _print(payload, args.json)
    return 0


def cmd_client_import(args):
    from xian_skills.client.sync import import_directory

    cfg = _cfg(args)
    payload = import_directory(_warehouse(cfg), args.channel, args.version, Path(args.src))
    _print(payload, args.json)
    return 0


def cmd_client_sync(args):
    from xian_skills.client.sync import sync_device

    cfg = _cfg(args)
    adb = _adb(cfg, args.device)
    include = [item for item in (args.include or "").split(",") if item]
    payload = sync_device(
        adb,
        _warehouse(cfg),
        args.channel,
        cfg.package(args.channel),
        yes=args.yes,
        include=include or None,
    )
    _print(payload, args.json)
    return 0


def cmd_client_snapshots(args):
    cfg = _cfg(args)
    payload = {"channel": args.channel, "snapshots": _warehouse(cfg).list_snapshots(args.channel)}
    _print(payload, args.json)
    return 0


def cmd_client_diff(args):
    from xian_skills.storage.warehouse import diff_manifests

    cfg = _cfg(args)
    warehouse = _warehouse(cfg)
    left = warehouse.read_snapshot(args.channel, args.left)
    right = warehouse.read_snapshot(args.channel, args.right)
    _print(diff_manifests(left, right), args.json)
    return 0


def cmd_client_materialize(args):
    cfg = _cfg(args)
    dest = _warehouse(cfg).export_snapshot(args.channel, args.snapshot, Path(args.dest))
    _print({"dest": str(dest)}, args.json)
    return 0


def cmd_lua_decode(args):
    from xian_skills.lua.decrypt import decode_raw, decode_tree

    inp = _p(args.input)
    out_path = _p(args.output)
    if args.raw:
        data = inp.read_bytes()
        out = decode_raw(data)
        out_path.parent.mkdir(parents=True, exist_ok=True)
        out_path.write_bytes(out)
        payload = {"output": str(out_path), "lj": out.startswith(b"\x1bLJ"), "size": len(out)}
    else:
        payload = decode_tree(inp, out_path, tag=args.tag, limit=args.limit)
    _print(payload, args.json)
    return 0


def cmd_lua_decompile(args):
    from xian_skills.lua.decompile import decompile_tree
    from xian_skills.tools.decompiler import resolve_decompiler

    cfg = _cfg(args)
    decompiler = resolve_decompiler(cfg.data.get("decompiler_path") or "") or Path(cfg.data.get("decompiler_path") or "")
    payload = decompile_tree(_p(args.input), _p(args.output), decompiler, limit=args.limit)
    _print(payload, args.json)
    return 0 if payload["fail"] == 0 else 3


def cmd_lua_tables(args):
    from xian_skills.lua.pipeline import export_tree

    payload = export_tree(_p(args.input), _p(args.output))
    _print(payload, args.json)
    return 0 if payload["fail"] == 0 else 3


def cmd_lua_constants(args):
    from xian_skills.lua.pipeline import dump_constants

    payload = dump_constants(_p(args.input))
    if args.output:
        out_path = _p(args.output)
        out_path.parent.mkdir(parents=True, exist_ok=True)
        out_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    _print({"strings": len(payload.get("strings") or []), "output": args.output, "error": payload.get("error")}, args.json)
    return 0


def cmd_lua_index(args):
    from xian_skills.lua.pipeline import build_index

    payload = build_index(_p(args.lua) if args.lua else None, _p(args.tables) if args.tables else None, _p(args.output))
    _print(payload, args.json)
    return 0


def cmd_query(args):
    from xian_skills.query.ask import ask, build_catalog, format_link_report, link_id, load_catalog
    from xian_skills.query.engine import query_index, query_table

    provenance = {"channel": args.channel, "version": args.version, "snapshot": args.snapshot}
    text_out = None
    if args.build_catalog:
        if not args.output:
            raise XianError("构建目录索引需要 --output 指定输出目录")
        payload = build_catalog(_p(args.build_catalog), _p(args.output), provenance)
    elif args.catalog and args.q and not args.link:
        payload = ask(load_catalog(_p(args.catalog)), args.q, limit=args.limit)
    elif args.link and (args.tables_dir or args.catalog):
        tables_dir = _p(args.tables_dir) if args.tables_dir else None
        if tables_dir is None and args.catalog:
            cat = load_catalog(_p(args.catalog))
            if not cat.get("tables_dir"):
                raise XianError("目录索引中缺少 tables_dir，请传入 --tables-dir")
            tables_dir = _p(cat["tables_dir"])
            provenance = {
                "channel": args.channel or cat.get("channel"),
                "version": args.version or cat.get("version"),
                "snapshot": args.snapshot or cat.get("snapshot"),
            }
        payload = link_id(
            tables_dir,
            args.link,
            provenance,
            limit=args.limit,
            mode=args.link_mode,
            max_depth=args.max_depth,
        )
        text_out = format_link_report(payload)
    elif args.table:
        payload = query_table(_p(args.table), args.field or None, args.op or None, args.value or None, limit=args.limit)
        payload.update({key: value for key, value in provenance.items() if value})
    elif args.index and args.q:
        payload = query_index(_p(args.index), args.kind, args.q, limit=args.limit)
        payload.update({key: value for key, value in provenance.items() if value})
    else:
        raise XianError("查询需要 --table、--catalog 加 --q、--index 加 --q，或 --link 加 --tables-dir/--catalog")
    _print(payload, args.json, text_out)
    return 0


def cmd_search(args):
    from xian_skills.query.engine import search_text

    payload = search_text(_p(args.root), args.q, limit=args.limit)
    _print(payload, args.json)
    return 0


def cmd_capture_start(args):
    from xian_skills.capture.session import Session, request_start

    request_start(args.yes)
    cfg = _cfg(args)
    warehouse = _warehouse(cfg)
    adb = _adb(cfg, args.device)
    out = Path(args.out) if args.out else warehouse.root / "captures" / args.session
    payload = Session(adb, out, args.session, profile=args.profile, rotate_mb=args.rotate_mb).run(minutes=args.minutes)
    _print(payload, args.json)
    return 0


def cmd_capture_stop(args):
    from xian_skills.capture.session import stop_session

    cfg = _cfg(args)
    if args.out:
        out = Path(args.out)
    elif args.session:
        out = _warehouse(cfg).root / "captures" / args.session
    else:
        lock = _warehouse(cfg).root / "captures" / "LOCK"
        if not lock.is_file():
            raise XianError("没有正在进行的抓包。请传入 --out 或 --session。")
        out = Path(json.loads(lock.read_text(encoding="utf-8"))["out"])
    adb = None
    try:
        adb = _adb(cfg, args.device)
    except XianError:
        adb = None
    _print(stop_session(out, adb), args.json)
    return 0


def cmd_capture_status(args):
    from xian_skills.capture.session import status

    cfg = _cfg(args)
    lock = _warehouse(cfg).root / "captures" / "LOCK"
    _print(status(lock), args.json)
    return 0


def cmd_capture_parse(args):
    from xian_skills.capture.session import parse_capture

    payload = parse_capture(Path(args.pcap), Path(args.output), profile=args.profile)
    _print(payload, args.json)
    return 0


def cmd_capture_stats(args):
    from xian_skills.capture.session import stats

    _print(stats(Path(args.jsonl)), args.json)
    return 0


def cmd_assets(args):
    from xian_skills.assets.export import export_path

    cfg = _cfg(args)
    payload = export_path(
        Path(args.input),
        Path(args.output),
        kind=args.kind,
        vgmstream=cfg.data.get("vgmstream_path") or "",
        ffmpeg=cfg.data.get("ffmpeg_path") or "",
        limit=args.limit,
    )
    _print(payload, args.json)
    return 0


def cmd_research_mijing(args):
    from xian_skills.research.mijing import summarize_jsonl

    _print(summarize_jsonl(Path(args.jsonl), me=args.me or None), args.json)
    return 0


def cmd_research_pvp(args):
    from xian_skills.research.pvp import coefs_from_table, evaluate, load_coef_note

    values = {
        "hitrate": args.hitrate,
        "dodge": args.dodge,
        "crit": args.crit,
        "crit_resist": args.crit_resist,
        "my_dim": args.my_dim,
        "op_dim": args.op_dim,
        "my_ex": args.my_ex,
        "op_ex": args.op_ex,
        "crit_damage": args.crit_damage,
        "op_crit_defense": args.op_crit_defense,
        "user_rank": args.user_rank,
        "skill_rank": args.skill_rank,
        "as_base": args.as_base,
        "as_grow": args.as_grow,
        "skill_level": args.skill_level,
        "endurance": args.endurance,
        "layers": args.layers,
    }
    loaded = coefs_from_table(Path(args.coefs)) if args.coefs else {"loaded": False, "coefs": {}}
    payload = evaluate(values, loaded.get("coefs") or None)
    payload["coef_file"] = loaded if args.coefs else load_coef_note(None)
    _print(payload, args.json)
    return 0


def cmd_research_plan(args):
    from xian_skills.research.plan import plan

    _print(plan(args.question), args.json)
    return 0


def cmd_research_init(args):
    from xian_skills.research.plan import init_script

    cfg = _cfg(args)
    root = Path(args.dir) if args.dir else _warehouse(cfg).root / "research"
    _print(init_script(root, args.name), args.json)
    return 0


def cmd_runtime(args):
    from xian_skills.runtime.probe import frida_inspect, list_game_processes, require_yes

    require_yes(args.yes)
    cfg = _cfg(args)
    adb = _adb(cfg, args.device)
    payload = list_game_processes(adb)
    if args.pid:
        adb.run(["-s", adb.serial, "forward", f"tcp:{args.frida_port}", f"tcp:{args.frida_port}"], timeout=20)
        payload["frida"] = frida_inspect(f"127.0.0.1:{args.frida_port}", args.pid)
    _print(payload, args.json)
    return 0


def cmd_events(args):
    from xian_skills.events.analyze import analyze, to_markdown

    report = analyze(Path(args.tables), Path(args.other) if args.other else None)
    if args.output:
        out_path = Path(args.output)
        out_path.parent.mkdir(parents=True, exist_ok=True)
        out_path.write_text(to_markdown(report), encoding="utf-8")
        report["output"] = args.output
    _print(report, args.json, None if args.json or not args.output else to_markdown(report))
    return 0


def cmd_updates_compare(args):
    from xian_skills.updates.report import compare_dirs

    _print(compare_dirs(Path(args.left), Path(args.right)), args.json)
    return 0


def cmd_updates_report(args):
    from xian_skills.updates.report import report_from_tables

    _print(report_from_tables(Path(args.left), Path(args.right), Path(args.output)), args.json)
    return 0


def cmd_updates_records(args):
    from xian_skills.updates.records import diff_table_tree, to_markdown

    report = diff_table_tree(
        Path(args.left),
        Path(args.right),
        {"label": args.left_label, "version": args.left_version, "path": args.left},
        {"label": args.right_label, "version": args.right_version, "path": args.right},
        args.relation,
    )
    if args.output:
        out_path = Path(args.output)
        out_path.parent.mkdir(parents=True, exist_ok=True)
        out_path.write_text(to_markdown(report), encoding="utf-8")
        json_path = out_path.with_suffix(".records.json") if out_path.suffix.lower() == ".json" else out_path.with_suffix(".json")
        json_path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
        report = {"out": args.output, "tables": len(report["tables"]), "relation": report["relation"], "warning": report["warning"]}
    _print(report, args.json)
    return 0


def cmd_updates_history(args):
    from xian_skills.updates.records import same_channel_history

    cfg = _cfg(args)
    snaps = _warehouse(cfg).list_snapshots(args.channel)
    _print(same_channel_history(snaps), args.json)
    return 0


def cmd_research_run(args):
    from xian_skills.research.run import run_question

    cfg = _cfg(args)
    history = _warehouse(cfg).list_snapshots(args.channel) if args.channel else []
    out = Path(args.output) if args.output else _warehouse(cfg).root / "research" / "latest"
    _print(run_question(args.question, Path(args.catalog), out, history), args.json)
    return 0


def cmd_cache_clean(args):
    if not args.yes:
        raise NeedConfirm("只会删除数据目录里的 cache。快照、抓包和研究笔记会保留。确认后加 --yes。")
    _print(_warehouse(_cfg(args)).clean_cache(), args.json)
    return 0


def cmd_install(args):
    from xian_skills.install.apply import install_skills, skills_source, write_receipt

    cfg = _cfg(args)
    platforms = [item.strip() for item in args.platform.split(",") if item.strip()] or [
        "claude-code",
        "codex",
        "cursor",
        "kimi-code",
        "kiro",
        "workbuddy",
        "doubao-work",
    ]
    install_user = args.user or not args.project
    _write_launcher()
    payload = install_skills(
        skills_source(args.source),
        Path.home(),
        _p(args.project) if args.project else None,
        platforms,
        force=args.force,
        backup_root=cfg.data_dir.parent / "backup",
        install_user=install_user,
    )
    write_receipt(cfg.data_dir.parent / "install.json", payload)
    _print(payload, args.json)
    return 0


def cmd_platforms(_args):
    from xian_skills.install.apply import PLATFORMS

    _print(PLATFORMS, _args.json)
    return 0


def _add_common(parser):
    parser.add_argument("--json", action="store_true", help="机器可读 JSON 输出")
    parser.add_argument("--config", default="", help="配置文件路径")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="xian", description="一念逍遥本地研究工具")
    parser.add_argument("--version", action="version", version=__version__)
    _add_common(parser)
    sub = parser.add_subparsers(dest="cmd", required=True)

    doctor = sub.add_parser("doctor", help="检查 Python、依赖、adb 和模拟器")
    doctor.add_argument("--no-device", action="store_true")
    doctor.set_defaults(func=cmd_doctor)

    init = sub.add_parser("init", help="写入配置并创建数据目录")
    init.add_argument("--data-dir", default="")
    init.add_argument("--adb", default="")
    init.add_argument("--device", default="")
    init.add_argument("--yes", action="store_true", help="在当前虚拟环境安装 Python 依赖")
    init.set_defaults(func=cmd_init)

    status = sub.add_parser("status", help="汇总可用、未验证和可以提问的例子")
    status.add_argument("--no-device", action="store_true")
    status.add_argument("--device", default="")
    status.set_defaults(func=cmd_status)

    verify = sub.add_parser("verify", help="运行基础测试；可选检查真实设备")
    verify.add_argument("--device-check", action="store_true")
    verify.add_argument("--device", default="")
    verify.set_defaults(func=cmd_verify)

    client = sub.add_parser("client", help="客户端发现、同步和快照")
    client_sub = client.add_subparsers(dest="client_cmd", required=True)
    discover = client_sub.add_parser("discover")
    discover.add_argument("--device", default="")
    discover.set_defaults(func=cmd_client_discover)
    version = client_sub.add_parser("version")
    version.add_argument("--device", default="")
    version.set_defaults(func=cmd_client_discover)
    imported = client_sub.add_parser("import-dir")
    imported.add_argument("--channel", required=True, choices=("official", "zhengdao"))
    imported.add_argument("--version", required=True)
    imported.add_argument("--src", required=True)
    imported.set_defaults(func=cmd_client_import)
    for name in ("pull", "sync"):
        sync = client_sub.add_parser(name)
        sync.add_argument("--channel", required=True, choices=("official", "zhengdao"))
        sync.add_argument("--device", default="")
        sync.add_argument("--include", default="", help="逗号分隔的相对路径，用于小范围提取")
        sync.add_argument("--yes", action="store_true")
        sync.set_defaults(func=cmd_client_sync)
    snaps = client_sub.add_parser("snapshots")
    snaps.add_argument("--channel", required=True, choices=("official", "zhengdao"))
    snaps.set_defaults(func=cmd_client_snapshots)
    diff = client_sub.add_parser("diff")
    diff.add_argument("--channel", required=True, choices=("official", "zhengdao"))
    diff.add_argument("--left", required=True)
    diff.add_argument("--right", required=True)
    diff.set_defaults(func=cmd_client_diff)
    materialize = client_sub.add_parser("materialize")
    materialize.add_argument("--channel", required=True, choices=("official", "zhengdao"))
    materialize.add_argument("--snapshot", required=True)
    materialize.add_argument("--dest", required=True)
    materialize.set_defaults(func=cmd_client_materialize)

    lua = sub.add_parser("lua", help="解密、反编译、导表和索引")
    lua_sub = lua.add_subparsers(dest="lua_cmd", required=True)
    decode = lua_sub.add_parser("decode")
    decode.add_argument("--input", required=True)
    decode.add_argument("--output", required=True)
    decode.add_argument("--tag", default="Lua64")
    decode.add_argument("--raw", action="store_true", help="输入已经是 TextAsset 字节，只做 XOR")
    decode.add_argument("--limit", type=int)
    decode.set_defaults(func=cmd_lua_decode)
    decompile = lua_sub.add_parser("decompile")
    decompile.add_argument("--input", required=True)
    decompile.add_argument("--output", required=True)
    decompile.add_argument("--limit", type=int)
    decompile.set_defaults(func=cmd_lua_decompile)
    tables = lua_sub.add_parser("tables")
    tables.add_argument("--input", required=True)
    tables.add_argument("--output", required=True)
    tables.set_defaults(func=cmd_lua_tables)
    constants = lua_sub.add_parser("constants")
    constants.add_argument("--input", required=True)
    constants.add_argument("--output", default="")
    constants.set_defaults(func=cmd_lua_constants)
    index = lua_sub.add_parser("index")
    index.add_argument("--lua", default="")
    index.add_argument("--tables", default="")
    index.add_argument("--output", required=True)
    index.set_defaults(func=cmd_lua_index)

    query = sub.add_parser("query", help="查询索引或一张表")
    query.add_argument("--index", default="")
    query.add_argument("--kind", default="table", choices=("file", "table", "field", "func"))
    query.add_argument("--q", default="")
    query.add_argument("--table", default="")
    query.add_argument("--field", default="")
    query.add_argument("--op", default="")
    query.add_argument("--value", default="")
    query.add_argument("--limit", type=int, default=50)
    query.add_argument("--catalog", default="")
    query.add_argument("--build-catalog", dest="build_catalog", default="")
    query.add_argument("--output", default="")
    query.add_argument("--link", default="")
    query.add_argument("--link-mode", dest="link_mode", default="all", choices=("all", "semantic"))
    query.add_argument("--max-depth", dest="max_depth", type=int, default=16)
    query.add_argument("--tables-dir", default="")
    query.add_argument("--channel", default="")
    query.add_argument("--version", default="")
    query.add_argument("--snapshot", default="")
    query.set_defaults(func=cmd_query)

    search = sub.add_parser("search", help="在 lua/json/文本里搜索")
    search.add_argument("--root", required=True)
    search.add_argument("--q", required=True)
    search.add_argument("--limit", type=int, default=40)
    search.set_defaults(func=cmd_search)

    capture = sub.add_parser("capture", help="采集和解析本机会话")
    capture_sub = capture.add_subparsers(dest="capture_cmd", required=True)
    start = capture_sub.add_parser("start")
    start.add_argument("--session", required=True)
    start.add_argument("--device", default="")
    start.add_argument("--out", default="")
    start.add_argument("--profile", default="full", choices=("full", "mijing", "pvp", "combat"))
    start.add_argument("--minutes", type=float, default=0)
    start.add_argument("--rotate-mb", type=int, default=16)
    start.add_argument("--yes", action="store_true")
    start.set_defaults(func=cmd_capture_start)
    stop = capture_sub.add_parser("stop")
    stop.add_argument("--session", default="")
    stop.add_argument("--out", default="")
    stop.add_argument("--device", default="")
    stop.set_defaults(func=cmd_capture_stop)
    capture_sub.add_parser("status").set_defaults(func=cmd_capture_status)
    parse = capture_sub.add_parser("parse")
    parse.add_argument("--pcap", required=True)
    parse.add_argument("--output", required=True)
    parse.add_argument("--profile", default="full")
    parse.set_defaults(func=cmd_capture_parse)
    stats = capture_sub.add_parser("stats")
    stats.add_argument("--jsonl", required=True)
    stats.set_defaults(func=cmd_capture_stats)

    assets = sub.add_parser("assets", help="导出图片、模型、音频和视频")
    assets_sub = assets.add_subparsers(dest="assets_cmd", required=True)
    export = assets_sub.add_parser("export")
    export.add_argument("--input", required=True)
    export.add_argument("--output", required=True)
    export.add_argument("--kind", default="all", choices=("all", "texture", "mesh", "audio", "video"))
    export.add_argument("--limit", type=int)
    export.set_defaults(func=cmd_assets)

    research = sub.add_parser("research", help="机制研究")
    research_sub = research.add_subparsers(dest="research_cmd", required=True)
    mijing = research_sub.add_parser("mijing")
    mijing.add_argument("--jsonl", required=True)
    mijing.add_argument("--me", default="")
    mijing.set_defaults(func=cmd_research_mijing)
    pvp = research_sub.add_parser("pvp")
    pvp.add_argument("--hitrate", type=float, default=0)
    pvp.add_argument("--dodge", type=float, default=0)
    pvp.add_argument("--crit", type=float, default=0)
    pvp.add_argument("--crit-resist", dest="crit_resist", type=float, default=0)
    pvp.add_argument("--my-dim", dest="my_dim", type=float, default=0)
    pvp.add_argument("--op-dim", dest="op_dim", type=float, default=0)
    pvp.add_argument("--my-ex", dest="my_ex", type=float, default=0)
    pvp.add_argument("--op-ex", dest="op_ex", type=float, default=0)
    pvp.add_argument("--crit-damage", dest="crit_damage", type=float, default=150)
    pvp.add_argument("--op-crit-defense", dest="op_crit_defense", type=float, default=0)
    pvp.add_argument("--user-rank", dest="user_rank", type=int, default=0)
    pvp.add_argument("--skill-rank", dest="skill_rank", type=int, default=0)
    pvp.add_argument("--as-base", dest="as_base", type=float)
    pvp.add_argument("--as-grow", dest="as_grow", type=float, default=0)
    pvp.add_argument("--skill-level", dest="skill_level", type=int, default=1)
    pvp.add_argument("--endurance", type=float, default=0)
    pvp.add_argument("--layers", type=int, default=1)
    pvp.add_argument("--coefs", default="")
    pvp.set_defaults(func=cmd_research_pvp)
    analyze = research_sub.add_parser("analyze")
    analyze.add_argument("--question", required=True)
    analyze.set_defaults(func=cmd_research_plan)
    init_script = research_sub.add_parser("init-script")
    init_script.add_argument("--name", required=True)
    init_script.add_argument("--dir", default="")
    init_script.set_defaults(func=cmd_research_init)
    run = research_sub.add_parser("run")
    run.add_argument("--question", required=True)
    run.add_argument("--catalog", required=True)
    run.add_argument("--channel", default="")
    run.add_argument("--output", default="")
    run.set_defaults(func=cmd_research_run)

    runtime = sub.add_parser("runtime", help="查看本机进程；可选 Frida 模块检查")
    runtime_sub = runtime.add_subparsers(dest="runtime_cmd", required=True)
    probe = runtime_sub.add_parser("probe")
    probe.add_argument("--device", default="")
    probe.add_argument("--pid", type=int)
    probe.add_argument("--frida-port", type=int, default=27042)
    probe.add_argument("--yes", action="store_true")
    probe.set_defaults(func=cmd_runtime)

    events = sub.add_parser("events", help="活动配置分析")
    events_sub = events.add_subparsers(dest="events_cmd", required=True)
    event_analyze = events_sub.add_parser("analyze")
    event_analyze.add_argument("--tables", required=True)
    event_analyze.add_argument("--other", default="")
    event_analyze.add_argument("--output", default="")
    event_analyze.set_defaults(func=cmd_events)

    updates = sub.add_parser("updates", help="版本对比和报告")
    updates_sub = updates.add_subparsers(dest="updates_cmd", required=True)
    compare = updates_sub.add_parser("compare")
    compare.add_argument("--left", required=True)
    compare.add_argument("--right", required=True)
    compare.set_defaults(func=cmd_updates_compare)
    report = updates_sub.add_parser("report")
    report.add_argument("--left", required=True)
    report.add_argument("--right", required=True)
    report.add_argument("--output", required=True)
    report.set_defaults(func=cmd_updates_report)
    records = updates_sub.add_parser("records")
    records.add_argument("--left", required=True)
    records.add_argument("--right", required=True)
    records.add_argument("--relation", default="cross-channel", choices=("cross-channel", "same-channel"))
    records.add_argument("--left-label", default="左侧")
    records.add_argument("--right-label", default="右侧")
    records.add_argument("--left-version", default="")
    records.add_argument("--right-version", default="")
    records.add_argument("--output", default="")
    records.set_defaults(func=cmd_updates_records)
    history = updates_sub.add_parser("history")
    history.add_argument("--channel", required=True, choices=("official", "zhengdao"))
    history.set_defaults(func=cmd_updates_history)

    tools = sub.add_parser("tools", help="准备外部工具")
    tools_sub = tools.add_subparsers(dest="tools_cmd", required=True)
    decompiler = tools_sub.add_parser("decompiler")
    decompiler.add_argument("--install", action="store_true")
    decompiler.add_argument("--yes", action="store_true")
    decompiler.set_defaults(func=cmd_tools_decompiler)

    cache = sub.add_parser("cache", help="只清理可再生缓存")
    cache_sub = cache.add_subparsers(dest="cache_cmd", required=True)
    clean = cache_sub.add_parser("clean")
    clean.add_argument("--yes", action="store_true")
    clean.set_defaults(func=cmd_cache_clean)

    install = sub.add_parser("install", help="安装技能到各个 Agent 平台目录")
    install.add_argument("--platform", default="", help="逗号分隔。默认七个平台")
    install.add_argument("--project", default="", help="安装到这个项目目录。只写了项目时，不改用户目录")
    install.add_argument("--user", action="store_true", help="安装到当前用户的技能目录")
    install.add_argument("--source", default="")
    install.add_argument("--force", action="store_true", help="目标已有不同内容时先备份再覆盖")
    install.set_defaults(func=cmd_install)

    platforms = sub.add_parser("platforms", help="查看平台适配说明")
    platforms.set_defaults(func=cmd_platforms)
    return parser


def _prepare_argv(argv):
    raw = list(sys.argv[1:] if argv is None else argv)
    as_json = False
    config = ""
    cleaned = []
    index = 0
    while index < len(raw):
        if raw[index] == "--json":
            as_json = True
            index += 1
            continue
        if raw[index] == "--config" and index + 1 < len(raw):
            config = raw[index + 1]
            index += 2
            continue
        cleaned.append(raw[index])
        index += 1
    return cleaned, as_json, config


def main(argv=None) -> int:
    parser = build_parser()
    cleaned, as_json, config = _prepare_argv(argv)
    args = parser.parse_args(cleaned)
    args.json = bool(as_json or getattr(args, "json", False))
    if config:
        args.config = config
    try:
        return args.func(args)
    except NeedConfirm as exc:
        _print({"error": str(exc), "confirm": True, **(exc.payload or {})}, getattr(args, "json", False))
        return exc.code
    except (XianError, EnvError) as exc:
        _print({"error": str(exc), **(exc.payload or {})}, getattr(args, "json", False))
        return exc.code
    except KeyError as exc:
        _print({"error": str(exc)}, getattr(args, "json", False))
        return 1


if __name__ == "__main__":
    raise SystemExit(main())

"""Turn decompiled config Lua into JSON and build a query index."""

from __future__ import annotations

import json
import re
from pathlib import Path

from xian_skills.errors import XianError
from xian_skills.lua import table_parser
from xian_skills.lua.lj_constants import dump_file, to_jsonable

RE_FUNC = re.compile(r"^\s*function\s+([A-Za-z_][\w\.:_]*)\s*\(", re.M)
RE_FUNC2 = re.compile(r"^\s*(?:local\s+)?([A-Za-z_][\w\.]*)\s*=\s*function\s*\(", re.M)
RE_RUNTIME_TABLE = re.compile(r"\b(?:function\b|for\s+\w+|while\s+|rerequire\s*\(|loadscript\s*\(|setmetatable\s*\(|require\s*\()")
RE_PART_PATTERN = re.compile(r'string\.format\(\s*"([^"]*_part%d[^"]*)"')


def simplify(obj):
    if isinstance(obj, dict):
        return {str(key): simplify(value) for key, value in obj.items()}
    if isinstance(obj, list):
        return [simplify(value) for value in obj]
    if isinstance(obj, float) and obj.is_integer() and abs(obj) < 2**53:
        return int(obj)
    return obj


def _inspect_source_status(path: Path, entries: int) -> tuple[str, str | None, str | None]:
    if entries > 0:
        return "nonempty", None, None
    try:
        src = path.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return "empty", None, None
    if RE_RUNTIME_TABLE.search(src):
        part_match = RE_PART_PATTERN.search(src)
        part_pattern = part_match.group(1) if part_match else None
        hint = "此表在客户端中由运行时逻辑或分片延迟加载（如 *_partN）动态生成；静态字面量导表不执行游戏 Lua 代码，顶层记录数为 0。"
        return "runtime_generated", part_pattern, hint
    return "empty", None, None


def export_table(path: Path, dest: Path, apply_defaults: bool = True, unpack_packed: bool = True) -> dict:
    path = Path(path)
    dest = Path(dest)
    if not path.is_file():
        raise XianError(f"没有 Lua 文件：{path}")
    table, parser = table_parser.load(path, apply_defaults=apply_defaults, unpack_packed=unpack_packed)
    if table is None or not isinstance(table, (dict, list)):
        return {"ok": False, "skipped": True, "data_status": "logic_skipped", "err": "no_table_returned", "src": str(path)}
    dest.parent.mkdir(parents=True, exist_ok=True)
    entries = len(table) if hasattr(table, "__len__") else 0
    data_status, part_pattern, runtime_hint = _inspect_source_status(path, entries)
    payload = {
        "source": str(path),
        "entries": entries,
        "data_status": data_status,
        "has_defaults": bool(getattr(parser, "defaults", None)),
        "key2idx": len(getattr(parser, "key2idx", {}) or {}),
        "data": simplify(table),
    }
    if part_pattern:
        payload["part_pattern"] = part_pattern
    if runtime_hint:
        payload["runtime_hint"] = runtime_hint
    dest.write_text(json.dumps(payload, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
    result = {"ok": True, "src": str(path), "dst": str(dest), "entries": entries, "data_status": data_status}
    if part_pattern:
        result["part_pattern"] = part_pattern
    return result


def export_tree(src: Path, dest: Path) -> dict:
    src = Path(src)
    dest = Path(dest)
    if not src.exists():
        raise XianError(f"输入不存在：{src}")
    files = [src] if src.is_file() else [path for path in sorted(src.rglob("*.lua")) if path.is_file()]
    ok = nonempty = runtime_generated = empty = skipped = fail = 0
    errors = []
    for path in files:
        rel = path.name + ".json" if src.is_file() else path.relative_to(src).with_suffix(path.suffix + ".json")
        try:
            record = export_table(path, dest / rel)
        except SyntaxError as exc:
            skipped += 1
            errors.append({"src": str(path), "err": f"SyntaxError: {exc}", "skipped": True, "data_status": "logic_skipped"})
            continue
        except Exception as exc:
            fail += 1
            errors.append({"src": str(path), "err": f"{type(exc).__name__}: {exc}"})
            continue
        if record.get("ok"):
            ok += 1
            status = record.get("data_status")
            if status == "runtime_generated":
                runtime_generated += 1
            elif status == "empty":
                empty += 1
            else:
                nonempty += 1
        elif record.get("skipped"):
            skipped += 1
        else:
            fail += 1
            errors.append(record)
    return {
        "ok": ok,
        "nonempty": nonempty,
        "runtime_generated": runtime_generated,
        "empty": empty,
        "skipped": skipped,
        "logic_skipped": skipped,
        "fail": fail,
        "completeness_note": (
            "静态导表不执行游戏 Lua 代码。ok 包含非空配置表 (nonempty)、运行时生成/分片主表 (runtime_generated) 和空表 (empty)；"
            "非表逻辑代码记入 skipped。"
        ),
        "errors": errors[:20],
    }


def dump_constants(path: Path) -> dict:
    return to_jsonable(dump_file(Path(path)))


def build_index(lua_root: Path, table_root: Path | None, dest: Path) -> dict:
    lua_root = Path(lua_root) if lua_root else None
    dest = Path(dest)
    dest.mkdir(parents=True, exist_ok=True)
    files = []
    functions: dict[str, list[str]] = {}
    if lua_root and lua_root.is_dir():
        for path in sorted(lua_root.rglob("*.lua")):
            if "_decompile_tmp" in path.parts:
                continue
            text = path.read_text(encoding="utf-8", errors="replace")
            rel = path.relative_to(lua_root).as_posix()
            names = RE_FUNC.findall(text) + RE_FUNC2.findall(text)
            files.append({"rel": rel, "bytes": path.stat().st_size, "funcs": len(names)})
            for name in names:
                functions.setdefault(name, [])
                if rel not in functions[name]:
                    functions[name].append(rel)
    tables = []
    if table_root and Path(table_root).is_dir():
        for path in sorted(Path(table_root).rglob("*.json")):
            try:
                payload = json.loads(path.read_text(encoding="utf-8"))
            except json.JSONDecodeError:
                continue
            data = payload.get("data") if isinstance(payload, dict) and "data" in payload else payload
            fields = []
            sample = None
            if isinstance(data, dict) and data:
                sample = next((val for val in data.values() if isinstance(val, dict)), None)
            elif isinstance(data, list) and data:
                sample = next((val for val in data if isinstance(val, dict)), None)
            if isinstance(sample, dict):
                fields = [str(key) for key in list(sample.keys())[:40]]
            entries = payload.get("entries") if isinstance(payload, dict) and "entries" in payload else (len(data) if isinstance(data, (dict, list)) else 0)
            data_status = (payload.get("data_status") if isinstance(payload, dict) else None) or ("nonempty" if entries else "empty")
            tables.append(
                {
                    "rel": path.relative_to(table_root).as_posix(),
                    "entries": entries,
                    "data_status": data_status,
                    "fields": fields,
                }
            )
    master = {"files": files, "tables": tables}
    (dest / "master_index.json").write_text(json.dumps(master, ensure_ascii=False), encoding="utf-8")
    (dest / "function_index.json").write_text(json.dumps(functions, ensure_ascii=False), encoding="utf-8")
    return {"lua_files": len(files), "functions": len(functions), "tables": len(tables), "dir": str(dest)}

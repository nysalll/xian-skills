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


def simplify(obj):
    if isinstance(obj, dict):
        return {str(key): simplify(value) for key, value in obj.items()}
    if isinstance(obj, list):
        return [simplify(value) for value in obj]
    if isinstance(obj, float) and obj.is_integer() and abs(obj) < 2**53:
        return int(obj)
    return obj


def export_table(path: Path, dest: Path, apply_defaults: bool = True, unpack_packed: bool = True) -> dict:
    path = Path(path)
    dest = Path(dest)
    if not path.is_file():
        raise XianError(f"没有 Lua 文件：{path}")
    table, parser = table_parser.load(path, apply_defaults=apply_defaults, unpack_packed=unpack_packed)
    if table is None:
        return {"ok": False, "skipped": True, "err": "no_table_returned", "src": str(path)}
    dest.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "source": str(path),
        "entries": len(table) if hasattr(table, "__len__") else 0,
        "has_defaults": bool(getattr(parser, "defaults", None)),
        "key2idx": len(getattr(parser, "key2idx", {}) or {}),
        "data": simplify(table),
    }
    dest.write_text(json.dumps(payload, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
    return {"ok": True, "src": str(path), "dst": str(dest), "entries": payload["entries"]}


def export_tree(src: Path, dest: Path) -> dict:
    src = Path(src)
    dest = Path(dest)
    if not src.exists():
        raise XianError(f"输入不存在：{src}")
    files = [src] if src.is_file() else [path for path in sorted(src.rglob("*.lua")) if path.is_file()]
    ok = skipped = fail = 0
    errors = []
    for path in files:
        rel = path.name + ".json" if src.is_file() else path.relative_to(src).with_suffix(path.suffix + ".json")
        try:
            record = export_table(path, dest / rel)
        except SyntaxError as exc:
            skipped += 1
            errors.append({"src": str(path), "err": f"SyntaxError: {exc}", "skipped": True})
            continue
        except Exception as exc:
            fail += 1
            errors.append({"src": str(path), "err": f"{type(exc).__name__}: {exc}"})
            continue
        if record.get("ok"):
            ok += 1
        elif record.get("skipped"):
            skipped += 1
        else:
            fail += 1
            errors.append(record)
    return {"ok": ok, "skipped": skipped, "fail": fail, "errors": errors[:20]}


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
            if isinstance(data, dict) and data:
                sample = next(iter(data.values()))
                if isinstance(sample, dict):
                    fields = [str(key) for key in list(sample.keys())[:40]]
            tables.append(
                {
                    "rel": path.relative_to(table_root).as_posix(),
                    "entries": payload.get("entries") if isinstance(payload, dict) else None,
                    "fields": fields,
                }
            )
    master = {"files": files, "tables": tables}
    (dest / "master_index.json").write_text(json.dumps(master, ensure_ascii=False), encoding="utf-8")
    (dest / "function_index.json").write_text(json.dumps(functions, ensure_ascii=False), encoding="utf-8")
    return {"lua_files": len(files), "functions": len(functions), "tables": len(tables), "dir": str(dest)}

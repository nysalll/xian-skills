"""Decompile LuaJIT bytecode with an external decompiler the user supplies."""

from __future__ import annotations

import shutil
import subprocess
import sys
import tempfile
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

from xian_skills.errors import EnvError, XianError

_RC_DLL_INIT_FAILED = -1073741502


def decompile_file(src: Path, dest: Path, decompiler: Path, timeout: int = 120) -> dict:
    src = Path(src)
    dest = Path(dest)
    if not src.is_file():
        raise XianError(f"没有字节码文件：{src}")
    with src.open("rb") as handle:
        magic = handle.read(3)
    if magic != b"\x1bLJ":
        dest.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(src, dest)
        return {"ok": True, "note": "plaintext_copied", "src": str(src), "dst": str(dest)}
    if not decompiler or not Path(decompiler).is_file():
        raise EnvError("未配置可用的 LuaJIT 反编译器。配置 decompiler_path 后再运行。仓库不附带反编译器。")
    work = Path(tempfile.mkdtemp(prefix="xian-lua-"))
    record = {"src": str(src), "dst": str(dest), "ok": False}
    try:
        tmp = work / "input.lua"
        out_dir = work / "out"
        out_dir.mkdir(parents=True)
        shutil.copyfile(src, tmp)
        flags = subprocess.CREATE_NO_WINDOW if sys.platform == "win32" else 0
        result = None
        for _attempt in range(3):
            result = subprocess.run(
                [str(decompiler), str(tmp), "-o", str(out_dir)],
                capture_output=True,
                timeout=timeout,
                creationflags=flags,
            )
            if result.returncode != _RC_DLL_INIT_FAILED:
                break
        produced = out_dir / "input.lua"
        if produced.is_file() and produced.stat().st_size > 0:
            dest.parent.mkdir(parents=True, exist_ok=True)
            shutil.move(str(produced), str(dest))
            record["ok"] = True
            record["size"] = dest.stat().st_size
        else:
            tail = ((result.stdout if result else b"") or b"")[-200:].decode("utf-8", "replace")
            record["err"] = tail.strip() or f"exit={result.returncode if result else 'none'}"
    finally:
        shutil.rmtree(work, ignore_errors=True)
    return record


def decompile_tree(src: Path, dest: Path, decompiler: Path, limit: int | None = None, workers: int = 4) -> dict:
    src = Path(src)
    dest = Path(dest)
    if not src.exists():
        raise XianError(f"输入不存在：{src}")
    if src.is_file():
        jobs = [(src, dest)]
    else:
        jobs = [(path, dest / path.relative_to(src)) for path in sorted(src.rglob("*.lua")) if path.is_file()]
    if limit is not None:
        jobs = jobs[:limit]
    pending = []
    skipped = 0
    for path, target in jobs:
        if target.is_file() and target.stat().st_size > 0:
            skipped += 1
            continue
        pending.append((path, target))
    if pending and (not decompiler or not Path(decompiler).is_file()):
        for path, _target in pending:
            with path.open("rb") as handle:
                if handle.read(3) == b"\x1bLJ":
                    raise EnvError("未配置可用的 LuaJIT 反编译器。配置 decompiler_path 后再运行。仓库不附带反编译器。")
    ok = fail = copied = 0
    errors = []

    def _one(job):
        path, target = job
        return decompile_file(path, target, decompiler)

    with ThreadPoolExecutor(max_workers=max(1, workers)) as pool:
        futures = [pool.submit(_one, job) for job in pending]
        for future in as_completed(futures):
            try:
                record = future.result()
            except EnvError:
                raise
            except Exception as exc:
                fail += 1
                errors.append({"err": str(exc)})
                continue
            if record.get("note") == "plaintext_copied":
                copied += 1
            elif record.get("ok"):
                ok += 1
            else:
                fail += 1
                errors.append(record)
    return {"ok": ok, "copied": copied, "skipped_existing": skipped, "fail": fail, "errors": errors[:20]}

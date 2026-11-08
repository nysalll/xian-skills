"""Client discovery, version reading, and snapshot sync."""

from __future__ import annotations

import hashlib
import json
import re
import shlex
from pathlib import Path

from xian_skills.device.adb import Adb
from xian_skills.errors import EnvError, NeedConfirm, XianError
from xian_skills.storage.warehouse import diff_manifests, import_tree, latest_complete, md5_file, utc_stamp

_VERSION_RE = re.compile(r"^\d+\.\d+\.\d+$")


def sh_quote(text: str) -> str:
    return "'" + text.replace("'", "'\\''") + "'"


def parse_version_text(text: str) -> dict:
    lines = []
    for raw in text.splitlines():
        line = raw.strip()
        if line:
            lines.append(line)
    current = ""
    for line in reversed(lines):
        if _VERSION_RE.match(line) or re.match(r"^\d+\.\d+", line):
            current = line
            break
    if not current and lines:
        current = lines[-1]
    return {
        "current_version": current,
        "current": current,
        "version_txt_line_count": len(lines),
        "history_count": len(lines),
        "history_tail": lines[-5:],
        "note": "version_txt_line_count 是客户端 version.txt 里的历史行数，不是本机快照份数。",
    }


def remote_roots(package: str) -> list[str]:
    return [
        f"/sdcard/Android/data/{package}/files",
        f"/storage/emulated/0/Android/data/{package}/files",
    ]


def shell_ok(result) -> bool:
    text = ((result.stdout or "") + (result.stderr or "")).lower()
    if result.returncode != 0:
        return False
    if "no such file" in text or "permission denied" in text or "not found" in text:
        return False
    return True


def discover_client(adb: Adb, channels: dict) -> dict:
    ident = adb.identity()
    found = []
    for name, spec in channels.items():
        package = spec["package"]
        path_result = adb.shell(f"pm path {shlex.quote(package)}", timeout=20)
        installed = shell_ok(path_result) and "package:" in (path_result.stdout or "")
        readable = None
        root = None
        version = None
        access_error = ""
        if installed:
            for candidate in remote_roots(package):
                probe = adb.shell(f"ls -d {sh_quote(candidate)}", timeout=20)
                if shell_ok(probe) and candidate in (probe.stdout or ""):
                    root = candidate
                    cat = adb.shell(f"cat {sh_quote(candidate + '/version.txt')}", timeout=20)
                    if shell_ok(cat) and (cat.stdout or "").strip():
                        version = parse_version_text(cat.stdout)
                        readable = True
                    else:
                        readable = True
                        access_error = ((cat.stderr or cat.stdout or "")).strip()[:200]
                    break
                access_error = ((probe.stderr or probe.stdout or "")).strip()[:200]
            if root is None:
                readable = False
        found.append(
            {
                "channel": name,
                "label": spec.get("label") or name,
                "package": package,
                "installed": installed,
                "data_root": root,
                "readable": readable,
                "version": version,
                "access_error": access_error,
            }
        )
    return {"device": adb.serial, "identity": ident, "clients": found}


def _safe_rel(rel: str) -> str:
    cleaned = (rel or "").strip().replace("\\", "/")
    while cleaned.startswith("./"):
        cleaned = cleaned[2:]
    if not cleaned or cleaned.startswith("/") or ":" in cleaned or ".." in Path(cleaned).parts:
        return ""
    return cleaned


def _parse_md5_lines(text: str, root: str = "") -> dict[str, str]:
    found = {}
    root_norm = root.replace("\\", "/").rstrip("/")
    for line in text.splitlines():
        line = line.strip()
        if len(line) < 34:
            continue
        digest = line[:32].lower()
        if not re.fullmatch(r"[0-9a-f]{32}", digest):
            continue
        rel = line[32:].strip().lstrip("*").strip().replace("\\", "/")
        if rel.startswith("./"):
            rel = rel[2:]
        if root_norm and rel.startswith(root_norm + "/"):
            rel = rel[len(root_norm) + 1 :]
        rel = _safe_rel(rel)
        if rel:
            found[rel] = digest
    return found


def parse_size_list(text: str, root: str = "") -> dict[str, int]:
    found = {}
    root_norm = root.replace("\\", "/").rstrip("/")
    for line in text.splitlines():
        if "|" not in line:
            continue
        size_text, path = line.split("|", 1)
        size_text = size_text.strip()
        if not size_text.isdigit():
            continue
        rel = path.strip().replace("\\", "/")
        if rel.startswith("./"):
            rel = rel[2:]
        if root_norm and rel.startswith(root_norm + "/"):
            rel = rel[len(root_norm) + 1 :]
        rel = _safe_rel(rel)
        if rel:
            found[rel] = int(size_text)
    return found


def listing_errors(text: str) -> list[str]:
    rows = []
    for line in (text or "").splitlines():
        lowered = line.lower()
        if "permission denied" in lowered or "not permitted" in lowered:
            rows.append(line.strip()[:240])
    return rows


def remote_sizes(adb: Adb, root: str) -> tuple[dict[str, int], list[str]]:
    script = f"cd {sh_quote(root)} && find . -type f -exec stat -c '%s|%n' {{}} +"
    result = adb.shell(script, timeout=300)
    sizes = parse_size_list(result.stdout or "", root)
    errors = listing_errors((result.stderr or "") + "\n" + (result.stdout or ""))
    if not sizes:
        detail = ((result.stderr or "") + (result.stdout or "")).strip()
        raise XianError(f"无法建立客户端文件清单：{detail[:300]}", code=3)
    return sizes, errors


def fingerprint_sizes(sizes: dict[str, int]) -> str:
    digest = hashlib.sha256()
    for rel in sorted(sizes):
        digest.update(rel.encode())
        digest.update(str(sizes[rel]).encode())
    return digest.hexdigest()


def load_journal(path: Path) -> dict[str, dict]:
    found = {}
    if not path.is_file():
        return found
    for line in path.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        item = json.loads(line)
        if item.get("rel"):
            found[item["rel"]] = item
    return found


def append_journal(path: Path, item: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(item, ensure_ascii=False) + "\n")


def remote_manifest(adb: Adb, root: str, only: list[str] | None = None) -> dict[str, str]:
    if only:
        found = {}
        for raw_rel in only:
            rel = _safe_rel(raw_rel)
            if not rel:
                raise XianError(f"非法相对路径：{raw_rel}", code=1)
            result = adb.shell(f"md5sum {sh_quote(root.rstrip('/') + '/' + rel)}", timeout=40)
            found.update(_parse_md5_lines(result.stdout or "", root))
        if found:
            return found
        raise XianError("没有算到指定文件的 md5。", code=3, payload={"include": only})
    script = (
        f"cd {sh_quote(root)} && "
        "(command -v md5sum >/dev/null 2>&1 && find . -type f -exec md5sum {} +) || "
        "(command -v toybox >/dev/null 2>&1 && toybox find . -type f | while IFS= read -r f; do toybox md5sum \"$f\"; done)"
    )
    result = adb.shell(script, timeout=1800)
    parsed = _parse_md5_lines(result.stdout or "", root)
    if parsed:
        return parsed
    listing = adb.shell(f"cd {sh_quote(root)} && find . -type f", timeout=180)
    if not shell_ok(listing):
        detail = ((listing.stderr or "") + (listing.stdout or "")).strip()
        raise XianError(f"无法读取客户端文件清单：{detail[:300]}", code=3)
    raise XianError(
        "设备上没有可用的 md5sum，已停止同步，避免把只看文件名的结果当成内容校验。",
        code=2,
        payload={"files_seen": len([ln for ln in (listing.stdout or "").splitlines() if ln.strip()])},
    )


def _known_files(warehouse, channel: str) -> dict[str, dict]:
    found = {}
    for snap in warehouse.list_snapshots(channel):
        data = warehouse.read_snapshot(channel, snap["id"])
        for item in data.get("files") or []:
            found[item["rel"]] = item
    return found


def _store_local(warehouse, local: Path) -> dict:
    size = local.stat().st_size
    digest = md5_file(local)
    sha = warehouse.put_file(local)
    return {"sha256": sha, "size": size, "md5": digest, "reused": False}


def sync_device(adb: Adb, warehouse, channel: str, package: str, yes: bool = False, include: list[str] | None = None) -> dict:
    if not yes:
        raise NeedConfirm(
            "这会把模拟器里的游戏文件复制到本地数据目录。检查环境或读取版本不算同意。"
            "已有快照不会被覆盖。确认复制范围后再加 --yes。",
            payload={"channel": channel, "package": package},
        )
    info = discover_client(adb, {channel: {"package": package, "label": channel}})
    client = info["clients"][0]
    if not client["installed"]:
        raise XianError(f"设备上没有安装 {package}", code=2)
    if not client["data_root"]:
        raise XianError(
            f"{package} 已安装，但外部数据目录不可读。请在模拟器里打开游戏并完成热更新，或确认模拟器允许 ADB 读取该目录。",
            code=2,
            payload=client,
        )
    root = client["data_root"]
    warehouse.ensure()
    if include:
        return _sync_selected(adb, warehouse, channel, client, root, include)
    return _sync_full(adb, warehouse, channel, client, root)


def _sync_selected(adb, warehouse, channel, client, root, include) -> dict:
    remote = remote_manifest(adb, root, only=include)
    known = _known_files(warehouse, channel)
    files, pulled, reused, failures = [], 0, 0, []
    staging = warehouse.root / "cache" / "pull" / "selected"
    for rel, digest in sorted(remote.items()):
        prev = known.get(rel)
        if prev and prev.get("md5") == digest and warehouse.has_blob(prev.get("sha256") or ""):
            files.append({**prev, "rel": rel, "md5": digest, "reused": True})
            reused += 1
            continue
        local = staging / rel
        try:
            adb.pull(f"{root}/{rel}", local, allow_empty=True)
            item = _store_local(warehouse, local)
            if item["md5"] != digest:
                failures.append({"rel": rel, "error": "md5 mismatch", "remote": digest, "local": item["md5"]})
                continue
            files.append({"rel": rel, **item})
            pulled += 1
            local.unlink(missing_ok=True)
        except XianError as exc:
            failures.append({"rel": rel, "error": str(exc)})
    return _commit_sync(
        warehouse, channel, client, adb, root, files, failures, pulled, reused,
        full=False, listing_errors=[], sizes=None,
    )


def _sync_full(adb, warehouse, channel, client, root) -> dict:
    sizes, denied = remote_sizes(adb, root)
    print(f"listed {len(sizes)} files denied={len(denied)}", flush=True)
    token = fingerprint_sizes(sizes)
    journal_path = warehouse.root / "cache" / "sync" / channel / token[:16] / "journal.jsonl"
    journal = load_journal(journal_path)
    known = _known_files(warehouse, channel)
    baseline = latest_complete(warehouse, channel)
    remote_md5 = {}
    if baseline or known:
        try:
            remote_md5 = remote_manifest(adb, root)
            print(f"remote md5 {len(remote_md5)}", flush=True)
        except XianError as exc:
            print(f"remote md5 unavailable: {exc}", flush=True)
            remote_md5 = {}
    tree = warehouse.root / "cache" / "sync" / channel / token[:16] / "tree"
    missing_local = [
        rel for rel, size in sizes.items()
        if not _journal_hit(journal, known, rel, size, remote_md5.get(rel), warehouse)
        and (not (tree / rel).is_file() or (tree / rel).stat().st_size != size)
    ]
    if missing_local and not tree.exists():
        print(f"pull tree, {len(missing_local)} files not reusable yet", flush=True)
        adb.pull_tree(root, tree, timeout=7200)
    elif missing_local:
        print(f"resume {len(missing_local)} files into existing tree", flush=True)
    files, pulled, reused, failures = [], 0, 0, []
    for index, (rel, size) in enumerate(sorted(sizes.items()), 1):
        hit = _journal_hit(journal, known, rel, size, remote_md5.get(rel), warehouse)
        if hit:
            files.append(hit)
            reused += 1
            continue
        local = tree / rel
        try:
            if not local.is_file() or local.stat().st_size != size:
                adb.pull(f"{root}/{rel}", local, allow_empty=(size == 0))
            if not local.is_file() or local.stat().st_size != size:
                failures.append({"rel": rel, "error": "size mismatch", "remote_size": size, "local_size": local.stat().st_size if local.is_file() else None})
                continue
            item = _store_local(warehouse, local)
            if remote_md5.get(rel) and item["md5"] != remote_md5[rel]:
                failures.append({"rel": rel, "error": "md5 mismatch", "remote": remote_md5[rel], "local": item["md5"]})
                continue
            record = {"rel": rel, **item}
            append_journal(journal_path, record)
            journal[rel] = record
            files.append(record)
            pulled += 1
        except XianError as exc:
            failures.append({"rel": rel, "error": str(exc)})
        if index % 200 == 0:
            print(f"progress {index}/{len(sizes)} pulled={pulled} reused={reused} failed={len(failures)}", flush=True)
    return _commit_sync(
        warehouse, channel, client, adb, root, files, failures, pulled, reused,
        full=True, listing_errors=denied, sizes=sizes,
    )


def _journal_hit(journal, known, rel, size, remote_digest, warehouse):
    in_journal = rel in journal
    prev = journal.get(rel) if in_journal else known.get(rel)
    if not prev or prev.get("size") != size or not warehouse.has_blob(prev.get("sha256") or ""):
        return None
    if not in_journal:
        if not remote_digest or not prev.get("md5") or prev["md5"] != remote_digest:
            return None
    elif remote_digest and prev.get("md5") and prev["md5"] != remote_digest:
        return None
    return {"rel": rel, "sha256": prev["sha256"], "size": size, "md5": prev.get("md5") or remote_digest, "reused": True}


def _commit_sync(warehouse, channel, client, adb, root, files, failures, pulled, reused, full, listing_errors, sizes) -> dict:
    complete = bool(full) and not failures and not listing_errors
    if sizes is not None and len(files) != len(sizes):
        complete = False
    baseline = latest_complete(warehouse, channel)
    version = (client.get("version") or {}).get("current") or "unknown"
    stamp = utc_stamp()
    safe_version = "".join(ch if ch.isalnum() or ch in "._-" else "_" for ch in version)
    snap_id = f"{safe_version}__{stamp}"
    manifest = {
        "version": version,
        "collected_at": stamp,
        "source": {"kind": "adb", "device": adb.serial, "package": client["package"], "data_root": root},
        "version_history_tail": (client.get("version") or {}).get("history_tail") or [],
        "files": files,
        "complete": complete,
        "incomplete": not complete,
        "scope": ["*"] if full else sorted({item["rel"] for item in files}),
        "unreadable": failures,
        "listing_errors": listing_errors,
    }
    warehouse.commit_snapshot(channel, snap_id, manifest)
    if complete and baseline:
        diff = diff_manifests(baseline, manifest)
    elif complete:
        diff = None
    else:
        diff = {"partial": True, "note": "这不是完整版本，不能当作整包对比基线。", "failed": len(failures)}
    payload = {
        "id": snap_id,
        "channel": channel,
        "version": version,
        "files": len(files),
        "pulled": pulled,
        "reused": reused,
        "failed": len(failures),
        "complete": complete,
        "incomplete": not complete,
        "diff_from_previous": diff,
    }
    if not complete:
        raise XianError(
            "快照已保存，但还有文件未通过校验或无法读取。历史完整快照没有被覆盖。",
            code=3,
            payload=payload,
        )
    return payload


def import_directory(warehouse, channel: str, version: str, src: Path) -> dict:
    return import_tree(warehouse, channel, version, src, source={"kind": "directory", "path": str(src)})


def file_fingerprint(paths: list[Path]) -> str:
    digest = hashlib.sha256()
    for path in paths:
        digest.update(path.name.encode())
        digest.update(path.read_bytes())
    return digest.hexdigest()

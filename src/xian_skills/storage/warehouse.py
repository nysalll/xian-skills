"""Content-addressed local warehouse.

Tool code and user data stay apart. Snapshots are immutable. Identical file
bytes are stored once. Cache cleanup never touches snapshots, captures, or
research notes.
"""

from __future__ import annotations

import hashlib
import json
import os
import shutil
from datetime import datetime, timezone
from pathlib import Path

from xian_skills.errors import XianError
from xian_skills.version import SCHEMA_VERSION, __version__

CHANNELS = ("official", "zhengdao")
PROTECTED = ("blobs", "official", "zhengdao", "captures", "research", "reports", "events", "assets", "lua", "indexes")


def utc_stamp() -> str:
    return datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ")


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1 << 20), b""):
            digest.update(chunk)
    return digest.hexdigest()


def md5_file(path: Path) -> str:
    digest = hashlib.md5()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1 << 20), b""):
            digest.update(chunk)
    return digest.hexdigest()


class Warehouse:
    def __init__(self, root: Path):
        self.root = Path(root)

    def ensure(self) -> None:
        for rel in (
            "blobs",
            "official/snapshots",
            "zhengdao/snapshots",
            "indexes",
            "captures",
            "assets",
            "research",
            "events",
            "reports",
            "cache",
            "lua",
        ):
            (self.root / rel).mkdir(parents=True, exist_ok=True)
        marker = self.root / "schema.json"
        payload = {
            "schema": SCHEMA_VERSION,
            "tool_version_created": __version__,
            "note": "Snapshots, captures and research notes are not cache.",
        }
        if not marker.exists():
            marker.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
            return
        current = json.loads(marker.read_text(encoding="utf-8"))
        if int(current.get("schema") or 1) > SCHEMA_VERSION:
            raise XianError(
                f"数据仓库 schema={current.get('schema')} 高于工具 schema={SCHEMA_VERSION}",
                code=2,
            )
        if int(current.get("schema") or 1) < SCHEMA_VERSION:
            current["schema"] = SCHEMA_VERSION
            current["upgraded_by"] = __version__
            marker.write_text(json.dumps(current, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    def channel_root(self, channel: str) -> Path:
        if channel not in CHANNELS:
            raise XianError(f"未知渠道 {channel}。可用：{', '.join(CHANNELS)}")
        return self.root / channel

    def blob_path(self, sha: str) -> Path:
        if not sha or len(sha) < 2 or "/" in sha or "\\" in sha or ".." in sha or Path(sha).name != sha:
            raise XianError(f"非法文件哈希 {sha}")
        return self.root / "blobs" / sha[:2] / sha

    def has_blob(self, sha: str) -> bool:
        return self.blob_path(sha).is_file()

    def put_file(self, path: Path) -> str:
        path = Path(path)
        digest = hashlib.sha256()
        tmp_dir = self.root / "cache" / "incoming"
        tmp_dir.mkdir(parents=True, exist_ok=True)
        tmp = tmp_dir / f"{os.getpid()}-{utc_stamp()}.part"
        with path.open("rb") as src, tmp.open("wb") as dst:
            for chunk in iter(lambda: src.read(1 << 20), b""):
                digest.update(chunk)
                dst.write(chunk)
        sha = digest.hexdigest()
        final = self.blob_path(sha)
        if final.is_file() and final.stat().st_size == tmp.stat().st_size:
            tmp.unlink(missing_ok=True)
            return sha
        final.parent.mkdir(parents=True, exist_ok=True)
        os.replace(tmp, final)
        return sha

    def materialize(self, sha: str, dest: Path) -> Path:
        src = self.blob_path(sha)
        if not src.is_file():
            raise XianError(f"仓库里没有文件 {sha}")
        dest = Path(dest)
        dest.parent.mkdir(parents=True, exist_ok=True)
        if dest.exists():
            return dest
        try:
            os.link(src, dest)
        except OSError:
            shutil.copyfile(src, dest)
        return dest

    def export_snapshot(self, channel: str, snap_id: str, dest: Path) -> Path:
        manifest = self.read_snapshot(channel, snap_id)
        dest = Path(dest).resolve()
        for item in manifest["files"]:
            rel = str(item.get("rel") or "").replace("\\", "/").lstrip("/")
            if not rel or ".." in Path(rel).parts or ":" in rel:
                raise XianError(f"非法相对路径 {item.get('rel')}")
            target = (dest / rel).resolve()
            if not target.is_relative_to(dest):
                raise XianError(f"路径越界 {item.get('rel')}")
            self.materialize(item["sha256"], target)
        return dest

    def snapshot_dir(self, channel: str, snap_id: str) -> Path:
        if not snap_id or "/" in snap_id or "\\" in snap_id or ".." in snap_id or snap_id.startswith("."):
            raise XianError(f"非法快照编号 {snap_id}")
        return self.channel_root(channel) / "snapshots" / snap_id

    def list_snapshots(self, channel: str) -> list[dict]:
        root = self.channel_root(channel) / "snapshots"
        if not root.is_dir():
            return []
        found = []
        for child in sorted(root.iterdir()):
            if not child.is_dir() or child.name.startswith("."):
                continue
            manifest_path = child / "manifest.json"
            if not manifest_path.is_file():
                continue
            data = json.loads(manifest_path.read_text(encoding="utf-8"))
            found.append(
                {
                    "id": child.name,
                    "version": data.get("version"),
                    "collected_at": data.get("collected_at"),
                    "files": len(data.get("files") or []),
                    "source": data.get("source"),
                    "incomplete": bool(data.get("incomplete")),
                    "complete": data.get("complete") is True,
                }
            )
        return found

    def read_snapshot(self, channel: str, snap_id: str) -> dict:
        path = self.snapshot_dir(channel, snap_id) / "manifest.json"
        if not path.is_file():
            raise XianError(f"没有快照 {channel}/{snap_id}")
        return json.loads(path.read_text(encoding="utf-8"))

    def latest_snapshot(self, channel: str) -> dict | None:
        snaps = self.list_snapshots(channel)
        if not snaps:
            return None
        return self.read_snapshot(channel, snaps[-1]["id"])

    def commit_snapshot(self, channel: str, snap_id: str, manifest: dict) -> Path:
        if not snap_id or "/" in snap_id or "\\" in snap_id or snap_id.startswith("."):
            raise XianError(f"非法快照编号 {snap_id}")
        final = self.snapshot_dir(channel, snap_id)
        if final.exists():
            raise XianError(f"快照已存在，拒绝覆盖：{channel}/{snap_id}")
        parent = final.parent
        parent.mkdir(parents=True, exist_ok=True)
        tmp = parent / f".incoming-{snap_id}"
        if tmp.exists():
            shutil.rmtree(tmp)
        tmp.mkdir(parents=True)
        manifest = dict(manifest)
        manifest["id"] = snap_id
        manifest["channel"] = channel
        manifest["schema"] = SCHEMA_VERSION
        manifest["tool_version"] = __version__
        (tmp / "manifest.json").write_text(
            json.dumps(manifest, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
        os.replace(tmp, final)
        return final

    def clean_cache(self) -> dict:
        cache = self.root / "cache"
        removed = 0
        if cache.is_dir():
            for child in cache.iterdir():
                if child.is_dir():
                    shutil.rmtree(child)
                else:
                    child.unlink()
                removed += 1
        cache.mkdir(parents=True, exist_ok=True)
        return {"removed": removed, "kept": list(PROTECTED)}


def latest_complete(warehouse: Warehouse, channel: str) -> dict | None:
    """A snapshot is a full version only when it was explicitly marked complete."""
    best = None
    for snap in warehouse.list_snapshots(channel):
        data = warehouse.read_snapshot(channel, snap["id"])
        if data.get("complete") is not True or data.get("incomplete"):
            continue
        if best is None or str(data.get("collected_at") or "") >= str(best.get("collected_at") or ""):
            best = data
    return best


def diff_manifests(left: dict, right: dict) -> dict:
    left_files = {item["rel"]: item for item in left.get("files") or []}
    right_files = {item["rel"]: item for item in right.get("files") or []}
    left_keys = set(left_files)
    right_keys = set(right_files)
    added = sorted(right_keys - left_keys)
    removed = sorted(left_keys - right_keys)
    changed = sorted(
        rel
        for rel in (left_keys & right_keys)
        if left_files[rel].get("sha256") != right_files[rel].get("sha256")
    )
    by_hash_left: dict[str, list[str]] = {}
    for rel, item in left_files.items():
        by_hash_left.setdefault(item.get("sha256") or "", []).append(rel)
    renamed = []
    for rel in added:
        sha = right_files[rel].get("sha256") or ""
        origins = [old for old in by_hash_left.get(sha, []) if old in removed or old in changed]
        if origins:
            renamed.append({"from": origins[0], "to": rel, "sha256": sha})
    return {
        "added": added,
        "removed": removed,
        "changed": changed,
        "renamed_candidates": renamed,
        "left_files": len(left_files),
        "right_files": len(right_files),
    }


def import_tree(warehouse: Warehouse, channel: str, version: str, src: Path, source: dict | None = None) -> dict:
    src = Path(src)
    if not src.is_dir():
        raise XianError(f"输入目录不存在：{src}")
    warehouse.ensure()
    files = []
    for path in sorted(p for p in src.rglob("*") if p.is_file()):
        rel = path.relative_to(src).as_posix()
        sha = warehouse.put_file(path)
        files.append(
            {
                "rel": rel,
                "sha256": sha,
                "size": path.stat().st_size,
                "md5": md5_file(path),
            }
        )
    stamp = utc_stamp()
    safe_version = "".join(ch if ch.isalnum() or ch in "._-" else "_" for ch in (version or "unknown"))
    snap_id = f"{safe_version}__{stamp}"
    manifest = {
        "version": version,
        "collected_at": stamp,
        "source": source or {"kind": "directory", "path": str(src)},
        "files": files,
        "incomplete": False,
        "complete": True,
        "scope": ["*"],
    }
    warehouse.commit_snapshot(channel, snap_id, manifest)
    return {"id": snap_id, "version": version, "files": len(files), "channel": channel}

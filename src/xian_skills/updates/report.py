"""Compare snapshots or exported trees and write an update report."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

from xian_skills.errors import XianError
from xian_skills.events.analyze import analyze, to_markdown
from xian_skills.storage.warehouse import diff_manifests


def _sha(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1 << 20), b""):
            digest.update(chunk)
    return digest.hexdigest()


def compare_dirs(left: Path, right: Path) -> dict:
    left = Path(left)
    right = Path(right)
    if not left.is_dir():
        raise XianError(f"左侧目录不存在：{left}")
    if not right.is_dir():
        raise XianError(f"右侧目录不存在：{right}")
    left_map = {path.relative_to(left).as_posix(): path for path in left.rglob("*") if path.is_file()}
    right_map = {path.relative_to(right).as_posix(): path for path in right.rglob("*") if path.is_file()}
    added = sorted(set(right_map) - set(left_map))
    removed = sorted(set(left_map) - set(right_map))
    changed = []
    for rel in sorted(set(left_map) & set(right_map)):
        if left_map[rel].stat().st_size != right_map[rel].stat().st_size or _sha(left_map[rel]) != _sha(right_map[rel]):
            changed.append(rel)
    return {"added": added, "removed": removed, "changed": changed, "left_files": len(left_map), "right_files": len(right_map)}


def compare_snapshots(left: dict, right: dict) -> dict:
    return diff_manifests(left, right)


def render_report(title: str, diff: dict, left_label: str, right_label: str, event_report: dict | None = None) -> str:
    lines = [
        f"# {title}",
        "",
        f"- 左侧：{left_label}",
        f"- 右侧：{right_label}",
        f"- 新增文件：{len(diff.get('added') or [])}",
        f"- 删除文件：{len(diff.get('removed') or [])}",
        f"- 内容变化：{len(diff.get('changed') or [])}",
        "",
        "文件差异只说明客户端资源变了。它不能单独证明服务器数值或活动规则已经按同样方式生效。",
        "",
        "## 新增",
        "",
    ]
    for rel in (diff.get("added") or [])[:80]:
        lines.append(f"- {rel}")
    lines.extend(["", "## 删除", ""])
    for rel in (diff.get("removed") or [])[:80]:
        lines.append(f"- {rel}")
    lines.extend(["", "## 变化", ""])
    for rel in (diff.get("changed") or [])[:80]:
        lines.append(f"- {rel}")
    if event_report:
        lines.extend(["", to_markdown(event_report)])
    lines.append("")
    return "\n".join(lines)


def write_report(path: Path, text: str, meta: dict) -> None:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")
    path.with_suffix(path.suffix + ".meta.json").write_text(
        json.dumps(meta, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )


def report_from_tables(left: Path, right: Path, out: Path, title: str = "版本更新报告") -> dict:
    diff = compare_dirs(left, right)
    events = None
    if any(path.suffix == ".json" for path in Path(right).rglob("*") if path.is_file()):
        try:
            events = analyze(Path(right), Path(left))
        except FileNotFoundError:
            events = None
    text = render_report(title, diff, str(left), str(right), events)
    write_report(out, text, {"left": str(left), "right": str(right), "diff_counts": {key: len(diff[key]) for key in ("added", "removed", "changed")}})
    return {"out": str(out), "diff": {key: len(diff[key]) for key in ("added", "removed", "changed")}}

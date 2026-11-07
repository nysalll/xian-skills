"""Copy skills into platform directories without touching unrelated skills."""

from __future__ import annotations

import hashlib
import json
import os
import shutil
import zipfile
from datetime import datetime, timezone
from pathlib import Path

from xian_skills.errors import XianError

PLATFORMS = {
    "claude-code": {
        "title": "Claude Code",
        "user": [".claude/skills"],
        "project": [".claude/skills"],
        "local_exec": "yes",
        "docs": "https://code.claude.com/docs/en/skills",
        "note": "个人技能在用户目录，项目技能在仓库的 .claude/skills。可以执行本地命令，受权限确认限制。",
    },
    "codex": {
        "title": "OpenAI Codex",
        "user": [".agents/skills", ".codex/skills"],
        "project": [".agents/skills"],
        "local_exec": "yes",
        "docs": "https://learn.chatgpt.com/docs/build-skills",
        "note": "当前文档把 ~/.agents/skills 作为用户技能目录，~/.codex/skills 仍被技能安装器使用。本地命令受沙箱和审批限制。",
    },
    "cursor": {
        "title": "Cursor",
        "user": [".cursor/skills", ".agents/skills"],
        "project": [".cursor/skills", ".agents/skills"],
        "local_exec": "yes",
        "docs": "https://cursor.com/docs/skills",
        "note": "Cursor 也会读取 Claude 和 Codex 的技能目录。本地命令需要用户批准。",
    },
    "kimi-code": {
        "title": "Kimi Code",
        "user": [".kimi-code/skills", ".agents/skills"],
        "project": [".kimi-code/skills", ".agents/skills"],
        "local_exec": "yes",
        "docs": "https://www.kimi.com/code/docs/kimi-code-cli/customization/skills.html",
        "note": "目录型 SKILL.md 必须写 name 和 description。这是 Kimi Code，不是 Kimi 网页聊天。",
    },
    "kiro": {
        "title": "Kiro",
        "user": [".kiro/skills"],
        "project": [".kiro/skills"],
        "local_exec": "desktop-cli",
        "docs": "https://kiro.dev/docs/skills/",
        "note": "IDE 和 CLI 可以加载技能并执行本地命令，受沙箱限制。Web 和手机端不能操作这台 Windows 上的 MuMu。",
    },
    "workbuddy": {
        "title": "腾讯 WorkBuddy",
        "user": [".workbuddy/skills"],
        "project": [".workbuddy/skills", ".codebuddy/skills"],
        "local_exec": "desktop-agent",
        "docs": "https://www.tencentcloud.com/zh/document/product/1316/84503",
        "note": "官方已确认的安装方式是技能页上传含 SKILL.md 的技能包。文件系统目录来自产品说明中的用户目录/项目目录，以及公开文档里的 .codebuddy/skills；上传 ZIP 是稳妥路径。",
        "zip": True,
    },
    "doubao-work": {
        "title": "豆包工作",
        "user": [],
        "project": [],
        "local_exec": "local-computer-mode",
        "docs": "https://www.doubao.com/work/docs/zh-cn/articles/081010973544-skills",
        "note": "豆包工作支持上传含 SKILL.md 的技能，并在“本地电脑”任务里运行命令。豆包普通对话没有这套本地研究能力。云电脑里的本机 MuMu 不可用。",
        "zip": True,
    },
}


def skills_source(explicit: str = "") -> Path:
    if explicit:
        path = Path(explicit)
        if not path.is_dir():
            raise XianError(f"技能目录不存在：{path}")
        return path
    candidates = []
    env = os.environ.get("XIAN_ROOT")
    if env:
        candidates.append(Path(env))
    candidates.append(Path.cwd())
    candidates.extend(Path.cwd().parents)
    candidates.extend(Path(__file__).resolve().parents)
    seen = set()
    for parent in candidates:
        parent = Path(parent)
        if parent in seen:
            continue
        seen.add(parent)
        candidate = parent / "skills"
        marker = parent / "pyproject.toml"
        if marker.is_file() and candidate.is_dir() and "xian-skills" in marker.read_text(encoding="utf-8"):
            return candidate
    raise XianError("找不到 skills 目录。请在 xian-skills 仓库里运行，或传入 --source。")


def _digest(path: Path) -> str:
    digest = hashlib.sha256()
    for file in sorted(item for item in path.rglob("*") if item.is_file()):
        digest.update(file.relative_to(path).as_posix().encode())
        digest.update(file.read_bytes())
    return digest.hexdigest()


def _copy_skill(src: Path, dest: Path, force: bool, backup_root: Path) -> str:
    if dest.exists():
        if _digest(src) == _digest(dest):
            return "unchanged"
        if not force:
            return "skipped-existing"
        stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ")
        backup = backup_root / f"{dest.name}-{stamp}"
        backup.parent.mkdir(parents=True, exist_ok=True)
        shutil.copytree(dest, backup)
        shutil.rmtree(dest)
    dest.parent.mkdir(parents=True, exist_ok=True)
    shutil.copytree(src, dest)
    return "installed"


def make_zip(source: Path, dest: Path) -> Path:
    dest.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(dest, "w", zipfile.ZIP_DEFLATED) as archive:
        for file in sorted(source.rglob("*")):
            if file.is_file() and "__pycache__" not in file.parts and not file.name.endswith(".pyc"):
                archive.write(file, file.relative_to(source.parent).as_posix())
    return dest


def install_skills(source: Path, home: Path, project: Path | None, platforms: list[str], force: bool, backup_root: Path, install_user: bool = True) -> dict:
    unknown = [name for name in platforms if name not in PLATFORMS]
    if unknown:
        raise XianError(f"未知平台：{', '.join(unknown)}")
    results = []
    for name in platforms:
        spec = PLATFORMS[name]
        for scope, roots in (("user", spec["user"]), ("project", spec["project"])):
            if scope == "user" and not install_user:
                continue
            if scope == "project" and project is None:
                continue
            base = home if scope == "user" else project
            for rel in roots:
                target_root = Path(base) / rel
                for skill in sorted(path for path in source.iterdir() if (path / "SKILL.md").is_file()):
                    status = _copy_skill(skill, target_root / skill.name, force, backup_root)
                    results.append({"platform": name, "scope": scope, "path": str(target_root / skill.name), "status": status})
        if spec.get("zip"):
            zip_path = backup_root.parent / "dist" / f"xian-skills-{name}.zip"
            make_zip(source, zip_path)
            results.append({"platform": name, "scope": "zip", "path": str(zip_path), "status": "zip-ready"})
    return {"results": results, "invocation_verified": False}


def write_receipt(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

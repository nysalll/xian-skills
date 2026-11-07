"""Export textures, meshes, audio, and video from local client files."""

from __future__ import annotations

import io
import json
import shutil
import subprocess
from pathlib import Path

from xian_skills.assets.usm import demux_one
from xian_skills.errors import EnvError, XianError
from xian_skills.lua.decrypt import strip_unity_header

_INVALID = '<>:"/\\|?*'


def sanitize(name: str, limit: int = 80) -> str:
    cleaned = "".join("_" if ch in _INVALID or ord(ch) < 32 else ch for ch in str(name)).strip().strip(".")
    return (cleaned or "noname")[:limit]


def export_unity_file(path: Path, dest: Path, kinds: set[str]) -> dict:
    try:
        import UnityPy
    except ImportError as exc:
        raise EnvError("缺少 UnityPy，无法导出贴图、网格或 Unity 音频。") from exc
    raw = strip_unity_header(Path(path).read_bytes())
    env = UnityPy.load(io.BytesIO(raw))
    saved = []
    errors = []
    for obj in env.objects:
        type_name = obj.type.name
        try:
            if type_name in {"Texture2D", "Sprite"} and "texture" in kinds:
                data = obj.read()
                image = data.image
                folder = dest / ("textures" if type_name == "Texture2D" else "sprites")
                folder.mkdir(parents=True, exist_ok=True)
                out = folder / f"{sanitize(getattr(data, 'm_Name', type_name))}.png"
                image.save(out)
                saved.append(str(out))
            elif type_name == "Mesh" and "mesh" in kinds:
                mesh = obj.read()
                folder = dest / "meshes"
                folder.mkdir(parents=True, exist_ok=True)
                out = folder / f"{sanitize(getattr(mesh, 'm_Name', 'mesh'))}.obj"
                exported = mesh.export() if hasattr(mesh, "export") else None
                if isinstance(exported, str):
                    out.write_text(exported, encoding="utf-8")
                elif isinstance(exported, bytes):
                    out.write_bytes(exported)
                else:
                    out = out.with_suffix(".json")
                    out.write_text(
                        json.dumps({"name": getattr(mesh, "m_Name", ""), "type": "Mesh"}, ensure_ascii=False),
                        encoding="utf-8",
                    )
                saved.append(str(out))
            elif type_name == "AudioClip" and "audio" in kinds:
                clip = obj.read()
                folder = dest / "audio"
                folder.mkdir(parents=True, exist_ok=True)
                samples = getattr(clip, "samples", None) or {}
                if isinstance(samples, dict) and samples:
                    for sample_name, blob in samples.items():
                        out = folder / f"{sanitize(sample_name)}.bin"
                        out.write_bytes(blob if isinstance(blob, bytes) else bytes(blob))
                        saved.append(str(out))
                else:
                    blob = getattr(clip, "m_AudioData", b"") or b""
                    if blob:
                        out = folder / f"{sanitize(getattr(clip, 'm_Name', 'audio'))}.bin"
                        out.write_bytes(blob if isinstance(blob, bytes) else bytes(blob))
                        saved.append(str(out))
        except Exception as exc:
            errors.append({"type": type_name, "error": f"{type(exc).__name__}: {exc}"})
    return {"file": str(path), "saved": saved, "errors": errors}


def decode_acb(acb: Path, dest: Path, vgmstream: Path) -> dict:
    if not vgmstream or not Path(vgmstream).is_file():
        raise EnvError("未配置 vgmstream。音频 bank 解码需要你自行准备 vgmstream-cli，仓库不附带该程序。")
    dest.mkdir(parents=True, exist_ok=True)
    template = str(dest / "?s_?n.wav")
    proc = subprocess.run(
        [str(vgmstream), "-s", "1", "-S", "0", "-o", template, str(acb)],
        capture_output=True,
        text=True,
        timeout=300,
        errors="replace",
    )
    files = sorted(path.name for path in dest.glob("*.wav"))
    log = ((proc.stdout or "") + (proc.stderr or "")).strip()
    if proc.returncode != 0 and not files:
        return {"bank": acb.name, "status": "error", "error": log[:300], "files": []}
    return {"bank": acb.name, "status": "ok" if files else "empty", "files": files, "error": None if files else log[:200]}


def transcode_ivf(path: Path, ffmpeg: Path) -> dict:
    if not ffmpeg or not Path(ffmpeg).is_file():
        found = shutil.which("ffmpeg")
        if not found:
            return {"file": str(path), "status": "missing_deps", "error": "没有 ffmpeg，已保留 .ivf"}
        ffmpeg = Path(found)
    out = path.with_suffix(".mp4")
    proc = subprocess.run(
        [str(ffmpeg), "-y", "-i", str(path), str(out)],
        capture_output=True,
        text=True,
        errors="replace",
    )
    return {"file": str(out), "status": "ok" if proc.returncode == 0 and out.is_file() else "error", "error": (proc.stderr or "")[-200:]}


def export_path(src: Path, dest: Path, kind: str = "all", vgmstream: str = "", ffmpeg: str = "", limit: int | None = None) -> dict:
    src = Path(src)
    dest = Path(dest)
    if not src.exists():
        raise XianError(f"输入不存在：{src}")
    kinds = {"texture", "mesh", "audio", "video"} if kind == "all" else {kind}
    files = [src] if src.is_file() else [path for path in src.rglob("*") if path.is_file()]
    if limit is not None:
        files = files[:limit]
    report = {"saved": [], "videos": [], "audio": [], "errors": [], "skipped": []}
    for path in files:
        suffix = path.suffix.lower()
        try:
            if suffix == ".unity3d" and kinds & {"texture", "mesh", "audio"}:
                result = export_unity_file(path, dest, kinds)
                report["saved"].extend(result["saved"])
                report["errors"].extend(result["errors"])
            elif suffix == ".usm" and "video" in kinds:
                result = demux_one(str(path), str(dest / "video"))
                report["videos"].append(result)
                if ffmpeg or shutil.which("ffmpeg"):
                    for item in result.get("outputs") or []:
                        if item["name"].endswith(".ivf"):
                            report["videos"].append(transcode_ivf(dest / "video" / item["name"], Path(ffmpeg) if ffmpeg else Path(shutil.which("ffmpeg"))))
            elif suffix == ".acb" and "audio" in kinds:
                report["audio"].append(decode_acb(path, dest / "audio_cri" / sanitize(path.stem), Path(vgmstream) if vgmstream else Path("")))
            else:
                report["skipped"].append(path.name)
        except EnvError:
            raise
        except Exception as exc:
            report["errors"].append({"file": str(path), "error": f"{type(exc).__name__}: {exc}"})
    report["skipped_count"] = len(report["skipped"])
    report["skipped"] = report["skipped"][:20]
    return report

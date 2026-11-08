"""Record and parse the user's own session. Raw captures stay in the data directory."""

from __future__ import annotations

import json
import os
import time
from collections import Counter
from datetime import datetime
from pathlib import Path

from xian_skills.capture.disk import wait_disk
from xian_skills.capture.remote import (
    ensure_root,
    list_remote_pcaps,
    pkill_tcpdump,
    remote_prefix,
    rm_remote,
    start_tcpdump,
)
from xian_skills.device.adb import Adb
from xian_skills.errors import NeedConfirm, XianError
from xian_skills.protocol.redact import redact

NOTICE = """此目录是本机私有抓包。
不要上传、不要提交到 Git，不要发给其他人。
文件里可能有角色标识和加密前的消息。口令、token、cookie 类字段在写入前会被替换成 [redacted]。
"""


class RedactingWriter:
    def __init__(self, inner: JsonlWriter):
        self.inner = inner

    @property
    def n(self):
        return self.inner.n

    @property
    def t0(self):
        return self.inner.t0

    @property
    def t1(self):
        return self.inner.t1

    def write_many(self, records):
        self.inner.write_many([redact(record) for record in records])

    def flush(self):
        self.inner.flush()

    def close(self):
        self.inner.close()


def _write_json(path: Path, obj) -> None:
    path.write_text(json.dumps(obj, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def _read_json(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


def _pid_alive(pid: int) -> bool:
    try:
        pid_int = int(pid)
    except (TypeError, ValueError):
        return False
    if pid_int <= 0:
        return False
    try:
        os.kill(pid_int, 0)
        return True
    except PermissionError:
        return True
    except OSError:
        return False


def _protocol():
    from xian_skills.protocol import zm

    return zm


class Session:
    def __init__(self, adb: Adb, out: Path, session: str, profile: str = "full", rotate_mb: int = 16, poll: float = 2.0):
        profiles = _protocol().PROFILES
        if profile not in profiles:
            raise XianError(f"未知 profile {profile}")
        self.adb = adb
        self.out = Path(out)
        self.session = session
        self.profile = profile
        self.rotate_mb = rotate_mb
        self.poll = poll
        self.chunks = self.out / "chunks"
        self.jsonl = self.out / "cap.jsonl"
        self.meta_path = self.out / "session.json"
        self.stop_path = self.out / "STOP"
        self.lock_path = self.out.parent / "LOCK"
        self.prefix = remote_prefix(session)
        self.asm = _protocol().Assembler(keep=profiles[profile])
        self.writer = None
        self.parsed = set()
        self.cap_proc = None
        self.rotate_ok = True

    def acquire_lock(self) -> None:
        self.lock_path.parent.mkdir(parents=True, exist_ok=True)
        if self.lock_path.exists():
            try:
                old = _read_json(self.lock_path)
            except Exception:
                old = {}
            if old.get("pid") and _pid_alive(old["pid"]):
                raise XianError(f"已有抓包在跑 pid={old.get('pid')} out={old.get('out')}", code=3)
        _write_json(self.lock_path, {"pid": os.getpid(), "out": str(self.out), "session": self.session})

    def release_lock(self) -> None:
        try:
            if self.lock_path.exists() and _read_json(self.lock_path).get("pid") == os.getpid():
                self.lock_path.unlink()
        except Exception:
            pass

    def parse_chunk(self, local: Path, tag: str) -> int:
        if tag in self.parsed:
            return 0
        before = self.asm.kept
        for ts, raw, linktype in _protocol().iter_pcap_file(local):
            self.asm.ingest(ts, raw, linktype)
        records = self.asm.flush()
        if records:
            self.writer.write_many(records)
        self.writer.flush()
        self.parsed.add(tag)
        self.save_meta()
        return self.asm.kept - before

    def save_meta(self, **extra) -> None:
        payload = {
            "session": self.session,
            "out": str(self.out),
            "device": self.adb.serial,
            "profile": self.profile,
            "parsed": sorted(self.parsed),
            "pid": os.getpid(),
        }
        payload.update(extra)
        _write_json(self.meta_path, payload)

    def harvest(self, include_current: bool) -> int:
        files = list_remote_pcaps(self.adb, self.prefix)
        if not include_current:
            files = files[:-1]
        gained = 0
        for index, remote in files:
            tag = f"{index:05d}"
            if tag in self.parsed:
                rm_remote(self.adb, remote)
                continue
            if not wait_disk():
                break
            local = self.chunks / f"{tag}.pcap"
            try:
                self.adb.pull(remote, local)
            except XianError:
                continue
            gained += self.parse_chunk(local, tag)
            rm_remote(self.adb, remote)
        return gained

    def run(self, minutes: float = 0) -> dict:
        self.out.mkdir(parents=True, exist_ok=True)
        self.chunks.mkdir(parents=True, exist_ok=True)
        (self.out / "PRIVATE.txt").write_text(NOTICE, encoding="utf-8")
        self.acquire_lock()
        if self.meta_path.exists():
            self.parsed = set(_read_json(self.meta_path).get("parsed") or [])
        self.writer = RedactingWriter(_protocol().JsonlWriter(self.jsonl))
        self.stop_path.unlink(missing_ok=True)
        started = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        self.save_meta(started=started, status="recording")
        try:
            ensure_root(self.adb)
            self.cap_proc, self.rotate_ok = start_tcpdump(self.adb, self.prefix, self.rotate_mb)
            deadline = time.time() + minutes * 60 if minutes and minutes > 0 else None
            while True:
                if self.stop_path.exists() or (deadline and time.time() >= deadline):
                    break
                if self.rotate_ok:
                    self.harvest(include_current=False)
                time.sleep(self.poll)
        finally:
            pkill_tcpdump(self.adb)
            if self.cap_proc and self.cap_proc.poll() is None:
                self.cap_proc.terminate()
            time.sleep(1)
            try:
                self.harvest(include_current=True)
            except Exception:
                pass
            if self.writer:
                tail = self.asm.flush(final=True)
                if tail:
                    self.writer.write_many(tail)
                self.writer.close()
            self.save_meta(ended=datetime.now().strftime("%Y-%m-%d %H:%M:%S"), status="done")
            self.release_lock()
        return {"out": str(self.out), "jsonl": str(self.jsonl), "frames": self.asm.kept, "decrypted": self.asm.decrypted, "encrypted": self.asm.still_encrypted}


def request_start(yes: bool) -> None:
    if yes:
        return
    raise NeedConfirm(
        "抓包会在模拟器里执行 adb root（如果当前不是 root）、启动 tcpdump，并把流量保存到本地数据目录。"
        "流量只留在本机，默认不上传。登录和验证码仍由你自己完成。确认后加 --yes。"
    )


def stop_session(out: Path, adb: Adb | None = None) -> dict:
    out = Path(out)
    (out / "STOP").write_text("1\n", encoding="utf-8")
    if adb is not None:
        try:
            pkill_tcpdump(adb)
        except Exception as exc:
            return {"stop_file": str(out / "STOP"), "pkill_error": str(exc)}
    return {"stop_file": str(out / "STOP")}


def status(lock_path: Path) -> dict:
    if not lock_path.exists():
        return {"status": "idle"}
    data = _read_json(lock_path)
    data["alive"] = _pid_alive(data.get("pid") or 0)
    data["status"] = "recording" if data["alive"] else "stale-lock"
    return data


def parse_capture(pcap: Path, out: Path, profile: str = "full") -> dict:
    pcap = Path(pcap)
    out = Path(out)
    if not pcap.is_file():
        raise XianError(f"没有 pcap：{pcap}")
    protocol = _protocol()
    if profile not in protocol.PROFILES:
        raise XianError(f"未知 profile {profile}")
    if pcap.stat().st_size >= 1_000_000 and not wait_disk(timeout=120):
        raise XianError("磁盘占用过高，稍后再解析", code=3)
    out.parent.mkdir(parents=True, exist_ok=True)
    if out.exists():
        out.unlink()
    asm, _writer = protocol.parse_files([pcap], out, profile=profile)
    _redact_file(out)
    return {
        "out": str(out),
        "frames": asm.kept,
        "seen": asm.frames,
        "decrypted": asm.decrypted,
        "encrypted": asm.still_encrypted,
        "gaps": asm.gaps,
    }


def _redact_file(path: Path) -> None:
    tmp = path.with_suffix(path.suffix + ".tmp")
    with path.open(encoding="utf-8") as src, tmp.open("w", encoding="utf-8") as dst:
        for line in src:
            if not line.strip():
                continue
            dst.write(json.dumps(redact(json.loads(line)), ensure_ascii=False) + "\n")
    os.replace(tmp, path)


def stats(jsonl: Path) -> dict:
    counts = Counter()
    total = 0
    encrypted = 0
    decrypted = 0
    with Path(jsonl).open(encoding="utf-8") as handle:
        for line in handle:
            if not line.strip():
                continue
            record = json.loads(line)
            total += 1
            if record.get("enc"):
                decrypted += 1
            message = record.get("msg")
            if isinstance(message, dict) and message.get("_encrypted"):
                encrypted += 1
                counts["<encrypted>"] += 1
            elif isinstance(message, list) and message and isinstance(message[0], str):
                counts[message[0]] += 1
            elif isinstance(message, str):
                counts[message] += 1
            else:
                counts["<unparsed>"] += 1
    return {
        "frames": total,
        "decrypted_flag": decrypted,
        "still_encrypted": encrypted,
        "top": counts.most_common(40),
    }

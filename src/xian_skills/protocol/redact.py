"""Redact credential-like fields before logs leave the capture directory."""

from __future__ import annotations

_EXACT = {
    "password",
    "passwd",
    "pwd",
    "token",
    "access_token",
    "refresh_token",
    "session",
    "session_key",
    "secret",
    "cookie",
    "authorization",
    "auth",
    "ticket",
}
_PARTS = ("password", "passwd", "token", "secret", "cookie", "session_key")


def sensitive_key(key: object) -> bool:
    text = str(key).strip().lower()
    if text in _EXACT:
        return True
    return any(part in text for part in _PARTS)


def redact(obj):
    if isinstance(obj, dict):
        cleaned = {}
        for key, value in obj.items():
            if sensitive_key(key):
                cleaned[key] = "[redacted]"
            elif key == "_body_hex":
                cleaned[key] = "[ciphertext-omitted]"
            else:
                cleaned[key] = redact(value)
        return cleaned
    if isinstance(obj, list):
        return [redact(item) for item in obj]
    return obj


def mask_rid(text: str) -> str:
    if not isinstance(text, str) or len(text) < 8:
        return text
    return text[:2] + "…" + text[-2:]

"""Framework-independent security primitives for the examination system."""
from __future__ import annotations

import base64
import hashlib
import hmac
import os
import time
from urllib.parse import quote


def generate_totp_secret(num_bytes: int = 20) -> str:
    if num_bytes < 16:
        raise ValueError("TOTP secrets should contain at least 128 bits of entropy.")
    return base64.b32encode(os.urandom(num_bytes)).decode("ascii").rstrip("=")


def totp_code(secret_value: str, for_time: float | None = None, interval: int = 30, digits: int = 6) -> str:
    secret_value = (secret_value or "").strip().replace(" ", "").upper()
    if not secret_value or interval <= 0 or digits < 6 or digits > 8:
        return ""
    padding = "=" * ((8 - len(secret_value) % 8) % 8)
    try:
        key = base64.b32decode(secret_value + padding, casefold=True)
    except Exception:
        return ""
    counter = int((time.time() if for_time is None else for_time) // interval)
    digest = hmac.new(key, counter.to_bytes(8, "big"), hashlib.sha1).digest()
    offset = digest[-1] & 0x0F
    number = (int.from_bytes(digest[offset : offset + 4], "big") & 0x7FFFFFFF) % (10**digits)
    return str(number).zfill(digits)


def verify_totp(secret_value: str, code: str, window: int = 1, for_time: float | None = None) -> bool:
    candidate = "".join(ch for ch in str(code or "") if ch.isdigit())
    if len(candidate) != 6:
        return False
    now = time.time() if for_time is None else for_time
    return any(hmac.compare_digest(totp_code(secret_value, now + (step * 30)), candidate) for step in range(-window, window + 1))


def totp_uri(secret_value: str, username: str, issuer: str = "Learn with Hemant Exam System") -> str:
    return (
        f"otpauth://totp/{quote(issuer)}:{quote(username)}"
        f"?secret={secret_value}&issuer={quote(issuer)}&digits=6&period=30"
    )

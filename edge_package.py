"""Tamper-evident package helpers for cloud-to-campus exam transfer.

The envelope is deliberately framework-independent so signatures can be
regression-tested without Flask or a database.
"""
from __future__ import annotations

import base64
import hashlib
import hmac
import json
from typing import Any

FORMAT = "LWH-EDGE-1"


def canonical_json(value: Any) -> bytes:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")


def package_id(payload: dict[str, Any]) -> str:
    return hashlib.sha256(canonical_json(payload)).hexdigest()[:24]


def make_envelope(payload: dict[str, Any], signing_key: str | bytes) -> dict[str, Any]:
    key = signing_key.encode("utf-8") if isinstance(signing_key, str) else signing_key
    if len(key) < 32:
        raise ValueError("Exam package signing key must contain at least 32 bytes.")
    pid = package_id(payload)
    signature = hmac.new(key, canonical_json(payload), hashlib.sha256).hexdigest()
    return {"format": FORMAT, "package_id": pid, "payload": payload, "signature": signature}


def verify_envelope(envelope: dict[str, Any], signing_key: str | bytes) -> dict[str, Any]:
    key = signing_key.encode("utf-8") if isinstance(signing_key, str) else signing_key
    if len(key) < 32:
        raise ValueError("Exam package signing key must contain at least 32 bytes.")
    if not isinstance(envelope, dict) or envelope.get("format") != FORMAT:
        raise ValueError("Unsupported exam package format.")
    payload = envelope.get("payload")
    if not isinstance(payload, dict):
        raise ValueError("Exam package payload is missing.")
    supplied = str(envelope.get("signature") or "")
    expected = hmac.new(key, canonical_json(payload), hashlib.sha256).hexdigest()
    if not supplied or not hmac.compare_digest(supplied, expected):
        raise ValueError("Exam package signature verification failed.")
    expected_id = package_id(payload)
    if str(envelope.get("package_id") or "") != expected_id:
        raise ValueError("Exam package identifier does not match its payload.")
    return payload

SEALED_FORMAT = "LWH-EDGE-SEALED-1"


def _fernet_key(signing_key: str | bytes) -> bytes:
    from cryptography.fernet import Fernet  # imported lazily for framework-independent tests/builds
    key = signing_key.encode("utf-8") if isinstance(signing_key, str) else signing_key
    if len(key) < 32:
        raise ValueError("Exam package signing key must contain at least 32 bytes.")
    derived = hashlib.sha256(key + b"|lwh-edge-encryption-v1|").digest()
    return base64.urlsafe_b64encode(derived)


def seal_envelope(payload: dict[str, Any], signing_key: str | bytes) -> dict[str, Any]:
    """Encrypt and authenticate an exam payload for transport to a campus node."""
    from cryptography.fernet import Fernet
    key = signing_key.encode("utf-8") if isinstance(signing_key, str) else signing_key
    if len(key) < 32:
        raise ValueError("Exam package signing key must contain at least 32 bytes.")
    pid = package_id(payload)
    ciphertext = Fernet(_fernet_key(key)).encrypt(canonical_json(payload)).decode("ascii")
    signed = f"{pid}|{ciphertext}".encode("utf-8")
    signature = hmac.new(key, signed, hashlib.sha256).hexdigest()
    return {"format": SEALED_FORMAT, "package_id": pid, "ciphertext": ciphertext, "signature": signature}


def open_sealed_envelope(envelope: dict[str, Any], signing_key: str | bytes) -> dict[str, Any]:
    """Verify, decrypt and validate a sealed campus exam package."""
    from cryptography.fernet import Fernet, InvalidToken
    key = signing_key.encode("utf-8") if isinstance(signing_key, str) else signing_key
    if len(key) < 32:
        raise ValueError("Exam package signing key must contain at least 32 bytes.")
    if not isinstance(envelope, dict) or envelope.get("format") != SEALED_FORMAT:
        raise ValueError("Unsupported sealed exam package format.")
    pid = str(envelope.get("package_id") or "")
    ciphertext = str(envelope.get("ciphertext") or "")
    supplied = str(envelope.get("signature") or "")
    expected = hmac.new(key, f"{pid}|{ciphertext}".encode("utf-8"), hashlib.sha256).hexdigest()
    if not supplied or not hmac.compare_digest(supplied, expected):
        raise ValueError("Exam package signature verification failed.")
    try:
        raw = Fernet(_fernet_key(key)).decrypt(ciphertext.encode("ascii"))
        payload = json.loads(raw.decode("utf-8"))
    except (InvalidToken, ValueError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise ValueError("Exam package could not be decrypted.") from exc
    if not isinstance(payload, dict) or package_id(payload) != pid:
        raise ValueError("Exam package identifier does not match its decrypted payload.")
    return payload

"""Framework-independent tamper-evident audit-chain helpers."""
from __future__ import annotations

import hashlib
from typing import Mapping, Any


def canonical_audit_text(value: Any) -> str:
    return str(value if value is not None else '').replace('\r\n', '\n').replace('\r', '\n')


def audit_event_hash(*, prev_hash: str = '', actor: str = '', action: str = '', entity_type: str = '', entity_id: str = '', details: str = '', created_at: str = '') -> str:
    """Return a deterministic SHA-256 digest for one audit event.

    Length-prefixing each field avoids delimiter ambiguity and keeps the digest
    deterministic across database engines.
    """
    fields = [prev_hash, actor, action, entity_type, entity_id, details, created_at]
    framed = ''.join(f'{len(canonical_audit_text(v).encode("utf-8"))}:' + canonical_audit_text(v) for v in fields)
    return hashlib.sha256(framed.encode('utf-8')).hexdigest()


def verify_audit_rows(rows: list[Mapping[str, Any]]) -> dict[str, Any]:
    """Verify an ordered list of already-sealed audit rows.

    `rows` must be oldest-to-newest. Unsealed legacy rows should be filtered by
    the caller and counted separately.
    """
    previous = ''
    checked = 0
    for row in rows:
        expected_prev = canonical_audit_text(row.get('prev_hash', ''))
        if expected_prev != previous:
            return {'valid': False, 'checked': checked, 'reason': 'previous hash mismatch'}
        expected = audit_event_hash(
            prev_hash=expected_prev,
            actor=row.get('actor', ''), action=row.get('action', ''),
            entity_type=row.get('entity_type', ''), entity_id=row.get('entity_id', ''),
            details=row.get('details', ''), created_at=row.get('created_at', ''),
        )
        if canonical_audit_text(row.get('event_hash', '')) != expected:
            return {'valid': False, 'checked': checked, 'reason': 'event hash mismatch'}
        previous = expected
        checked += 1
    return {'valid': True, 'checked': checked, 'reason': ''}

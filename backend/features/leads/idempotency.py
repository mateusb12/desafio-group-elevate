"""Identificação de reenvios do recebimento de leads."""

import hashlib
import json
from uuid import UUID

from sqlalchemy import text
from sqlalchemy.orm import Session


def normalize_idempotency_key(raw: str | None) -> str | None:
    if not raw:
        return None

    try:
        value = UUID(raw.strip())
    except (ValueError, TypeError, AttributeError):
        return None

    if value.version != 4:
        return None

    return str(value)


def calculate_payload_hash(payload: dict) -> str:
    canonical = json.dumps(
        payload,
        sort_keys=True,
        ensure_ascii=False,
        separators=(",", ":"),
    )
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def acquire_idempotency_lock(db: Session, key: str) -> None:
    # Mesmo UUID -> mesmo lock no PostgreSQL.
    # Locks de chaves diferentes não bloqueiam uns aos outros.
    lock_id = int.from_bytes(
        UUID(key).bytes[:8],
        byteorder="big",
        signed=True,
    )

    db.execute(
        text("SELECT pg_advisory_xact_lock(:lock_id)"),
        {"lock_id": lock_id},
    )

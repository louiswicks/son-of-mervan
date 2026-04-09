"""
Idempotency key helpers for financial mutation endpoints.

Usage:
    key = request.headers.get("X-Idempotency-Key")
    if key:
        if len(key) > 256:
            raise HTTPException(422, "X-Idempotency-Key must be ≤256 characters")
        key_hash = compute_key_hash(user_id, key)
        cached = get_cached_response(db, key_hash)
        if cached is not None:
            return cached  # replay

    # ... do the real work ...

    if key:
        save_response(db, user_id, key, request_path, response_dict)
"""
import hashlib
import json
from datetime import datetime, timedelta
from sqlalchemy.orm import Session

IDEMPOTENCY_TTL_HOURS = 24


def compute_key_hash(user_id: int, client_key: str) -> str:
    """Return the SHA-256 hex digest of '<user_id>:<client_key>'."""
    raw = f"{user_id}:{client_key}"
    return hashlib.sha256(raw.encode()).hexdigest()


def get_cached_response(db: Session, key_hash: str) -> dict | None:
    """
    Look up an existing idempotency record by key_hash.
    Returns the deserialised response dict if found and not expired,
    otherwise returns None.
    """
    from database import IdempotencyRecord  # local import avoids circular dependency

    record = (
        db.query(IdempotencyRecord)
        .filter(IdempotencyRecord.key_hash == key_hash)
        .first()
    )
    if record is None:
        return None

    age = datetime.utcnow() - record.created_at
    if age > timedelta(hours=IDEMPOTENCY_TTL_HOURS):
        # Expired — delete stale record so the key can be reused
        db.delete(record)
        db.commit()
        return None

    return json.loads(record.response_body)


def save_response(
    db: Session,
    user_id: int,
    client_key: str,
    request_path: str,
    response: dict,
) -> None:
    """
    Persist an idempotency record.  If the key_hash already exists (race condition
    between two simultaneous identical requests) the IntegrityError is silently
    swallowed — the first writer wins.
    """
    from database import IdempotencyRecord  # local import avoids circular dependency
    from sqlalchemy.exc import IntegrityError

    key_hash = compute_key_hash(user_id, client_key)
    record = IdempotencyRecord(
        key_hash=key_hash,
        user_id=user_id,
        request_path=request_path,
        response_body=json.dumps(response),
        created_at=datetime.utcnow(),
    )
    try:
        db.add(record)
        db.commit()
    except IntegrityError:
        db.rollback()

from __future__ import annotations

import asyncio
import hashlib
import json
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from sqlalchemy import select
from sqlalchemy.orm import Session

from rag_workbench.adapters.models import IdempotencyRecord
from rag_workbench.domain.rules import validate_idempotency_key

_locks: dict[str, asyncio.Lock] = {}


@asynccontextmanager
async def operation_lock(operation: str, owner_id: str, key: str) -> AsyncIterator[None]:
    validate_idempotency_key(key)
    lock_key = f"{operation}:{owner_id}:{key}"
    lock = _locks.setdefault(lock_key, asyncio.Lock())
    async with lock:
        yield


def fingerprint(value: dict) -> str:
    serialized = json.dumps(value, sort_keys=True, ensure_ascii=False, separators=(",", ":"))
    return hashlib.sha256(serialized.encode("utf-8")).hexdigest()


def find_record(
    session: Session, operation: str, owner_id: str, key: str
) -> IdempotencyRecord | None:
    return session.scalar(
        select(IdempotencyRecord).where(
            IdempotencyRecord.operation_type == operation,
            IdempotencyRecord.owner_id == owner_id,
            IdempotencyRecord.key == key,
        )
    )


def check_fingerprint(record: IdempotencyRecord, expected: str) -> None:
    if record.fingerprint != expected:
        raise ValueError("idempotency_key_conflict")

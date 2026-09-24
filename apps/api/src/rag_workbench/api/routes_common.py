from __future__ import annotations

import uuid
from datetime import UTC, datetime

from fastapi import Request
from sqlalchemy import select
from sqlalchemy.orm import Session

from rag_workbench.adapters.models import (
    ConversationRecord,
    DocumentRecord,
    KnowledgeBaseRecord,
    RunRecord,
)
from rag_workbench.api.errors import _CATALOG, ApiProblem


def new_id() -> str:
    return str(uuid.uuid4())


def now_utc() -> datetime:
    return datetime.now(UTC)


def raise_code(code: str, run_id: str | None = None) -> None:
    status, _title, retryable = _CATALOG.get(code, _CATALOG["internal_error"])
    detail = {
        "invalid_request": "The request did not pass validation.",
        "resource_not_found": "The requested resource was not found.",
        "invalid_state_transition": "The requested state transition is not allowed.",
        "idempotency_key_conflict": (
            "This idempotency key was already used for different request content."
        ),
        "conversation_busy": "This conversation already has an active answer run.",
        "file_too_large": "The uploaded file exceeds the configured size limit.",
        "unsupported_file": "The file type is not supported.",
        "file_signature_mismatch": "The file contents do not match the file extension.",
        "invalid_cursor": "The event cursor is outside the available range.",
        "invalid_sse_cursor": "The SSE cursor is invalid for this run.",
        "runner_busy": "The local run dispatcher has no available capacity.",
        "storage_unavailable": (
            "The upload could not be finalized. The operation can be retried with the same key."
        ),
    }.get(code, "The request could not be completed.")
    raise ApiProblem(status, code, detail, retryable, run_id)


def require_kb(session: Session, knowledge_base_id: str) -> KnowledgeBaseRecord:
    value = session.get(KnowledgeBaseRecord, knowledge_base_id)
    if value is None:
        raise_code("resource_not_found")
    return value


def require_document(session: Session, document_id: str) -> DocumentRecord:
    value = session.get(DocumentRecord, document_id)
    if value is None:
        raise_code("resource_not_found")
    return value


def require_conversation(session: Session, conversation_id: str) -> ConversationRecord:
    value = session.get(ConversationRecord, conversation_id)
    if value is None:
        raise_code("resource_not_found")
    return value


def require_run(session: Session, run_id: str) -> RunRecord:
    value = session.get(RunRecord, run_id)
    if value is None:
        raise_code("resource_not_found")
    return value


def page_window(page: int, page_size: int) -> tuple[int, int]:
    if page < 1 or not 1 <= page_size <= 100:
        raise_code("invalid_request")
    return (page - 1) * page_size, page_size


def paged_query(session: Session, model, page: int, page_size: int, statement=None) -> dict:
    from sqlalchemy import func

    offset, limit = page_window(page, page_size)
    query = statement if statement is not None else select(model)
    count_query = select(func.count()).select_from(query.subquery())
    total = session.scalar(count_query) or 0
    rows = session.scalars(query.offset(offset).limit(limit)).all()
    return {"items": rows, "page": page, "page_size": page_size, "total": total}


def request_id(request: Request) -> str:
    return getattr(request.state, "request_id", "unknown")

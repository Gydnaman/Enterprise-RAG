from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, Header, Request
from sqlalchemy import select
from sqlalchemy.orm import Session

from rag_workbench.adapters.database import get_session
from rag_workbench.adapters.fixtures import MockKnowledgeRetriever
from rag_workbench.adapters.models import (
    DocumentRecord,
    IdempotencyRecord,
    RunRecord,
)
from rag_workbench.api.routes_common import new_id, now_utc, raise_code, require_kb
from rag_workbench.api.schemas import RetrievalDebugRequest, RetrievalDebugResult
from rag_workbench.application.idempotency import (
    check_fingerprint,
    find_record,
    fingerprint,
    operation_lock,
)
from rag_workbench.application.run_events import append_event
from rag_workbench.domain.rules import validate_idempotency_key

router = APIRouter()


@router.post("/retrieval/debug", response_model=RetrievalDebugResult, status_code=201)
async def debug_retrieval(
    body: RetrievalDebugRequest,
    request: Request,
    idempotency_key: Annotated[str, Header(alias="Idempotency-Key", min_length=1, max_length=128)],
    session: Session = Depends(get_session),
):
    try:
        validate_idempotency_key(idempotency_key)
    except ValueError:
        raise_code("invalid_request")
    kb = require_kb(session, body.knowledge_base_id)
    filters = body.document_ids or []
    if filters:
        documents = session.scalars(
            select(DocumentRecord).where(DocumentRecord.id.in_(filters))
        ).all()
        valid = {
            item.id
            for item in documents
            if item.knowledge_base_id == kb.id and item.is_fixture and item.status == "ready"
        }
        if valid != set(filters):
            raise_code("invalid_request")
    operation_fingerprint = fingerprint(body.model_dump(mode="json", by_alias=True))
    async with operation_lock("retrieval", kb.id, idempotency_key):
        existing = find_record(session, "retrieval", kb.id, idempotency_key)
        if existing is not None:
            try:
                check_fingerprint(existing, operation_fingerprint)
            except ValueError:
                raise_code("idempotency_key_conflict")
            return {
                "run_id": existing.private_data.get("runId", existing.resource_id),
                "mode": "mock",
                "query": body.query,
                "evidence": existing.private_data.get("evidence", []),
            }

        run_id = new_id()
        run = RunRecord(
            id=run_id,
            kind="retrieval",
            status="running",
            mode="mock",
            subject={"kind": "retrieval", "knowledgeBaseId": kb.id},
            started_at=now_utc(),
        )
        session.add(run)
        append_event(
            session,
            run,
            "run_started",
            "retrieval",
            "running",
            {"kind": "retrieval", "mode": "mock"},
        )
        evidence = MockKnowledgeRetriever(session).retrieve(
            kb.id, body.query.strip(), filters, body.top_k
        )
        refs = [
            {
                "revisionId": value["revision_id"],
                "chunkId": value["chunk_id"],
                "rank": value["rank"],
                "score": value["score"],
                "quote": value["snippet"][:600],
            }
            for value in evidence
        ]
        append_event(
            session,
            run,
            "retrieval_completed",
            "retrieval",
            "completed",
            {
                "evidenceCount": len(evidence),
                "evidenceRefs": refs,
            },
        )
        append_event(
            session, run, "run_completed", "retrieval", "completed", {"resultStatus": "completed"}
        )
        run.status = "completed"
        run.result_status = "completed"
        run.finished_at = now_utc()
        record = IdempotencyRecord(
            id=new_id(),
            operation_type="retrieval",
            owner_id=kb.id,
            key=idempotency_key,
            fingerprint=operation_fingerprint,
            resource_id=run_id,
            status="completed",
            private_data={"runId": run_id, "evidence": evidence},
        )
        session.add(record)
        session.commit()
        return {"run_id": run.id, "mode": "mock", "query": body.query.strip(), "evidence": evidence}

from __future__ import annotations

import asyncio
import json
import time
from typing import Annotated

from fastapi import APIRouter, Depends, Header, Query, Request
from fastapi.responses import StreamingResponse
from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session

from rag_workbench.adapters.database import get_session
from rag_workbench.adapters.models import (
    ConversationRecord,
    DocumentRecord,
    RunEventRecord,
    RunRecord,
)
from rag_workbench.api.routes_common import page_window, raise_code, require_run
from rag_workbench.api.schemas import Page, ProviderStatus, Run, RunEvent, RunSnapshot
from rag_workbench.application.serialization import event_dict, run_dict

router = APIRouter()


@router.get("/runs", response_model=Page[Run])
def list_runs(
    page: Annotated[int, Query(ge=1)] = 1,
    page_size: Annotated[int, Query(alias="pageSize", ge=1, le=100)] = 50,
    knowledge_base_id: str | None = Query(default=None, alias="knowledgeBaseId"),
    kind: str | None = None,
    status: str | None = None,
    session: Session = Depends(get_session),
):
    statement = select(RunRecord)
    if kind:
        if kind not in {"upload", "demo_trace", "retrieval", "answer"}:
            raise_code("invalid_request")
        statement = statement.where(RunRecord.kind == kind)
    if status:
        if status not in {"queued", "running", "completed", "failed"}:
            raise_code("invalid_request")
        statement = statement.where(RunRecord.status == status)
    if knowledge_base_id:
        knowledge_base_documents = select(DocumentRecord.id).where(
            DocumentRecord.knowledge_base_id == knowledge_base_id
        )
        knowledge_base_conversations = select(ConversationRecord.id).where(
            ConversationRecord.knowledge_base_id == knowledge_base_id
        )
        statement = statement.where(
            or_(
                RunRecord.subject["knowledgeBaseId"].as_string() == knowledge_base_id,
                RunRecord.subject["documentId"].as_string().in_(knowledge_base_documents),
                RunRecord.demo_document_id.in_(knowledge_base_documents),
                RunRecord.conversation_id.in_(knowledge_base_conversations),
            )
        )
    offset, limit = page_window(page, page_size)
    total = (
        session.scalar(select(func.count()).select_from(statement.order_by(None).subquery())) or 0
    )
    runs = session.scalars(
        statement.order_by(RunRecord.created_at.desc(), RunRecord.id.desc())
        .offset(offset)
        .limit(limit)
    ).all()
    return {
        "items": [run_dict(value) for value in runs],
        "page": page,
        "page_size": page_size,
        "total": total,
    }


@router.get("/runs/{run_id}", response_model=RunSnapshot)
def get_run(
    run_id: str,
    after_sequence: Annotated[int, Query(alias="afterSequence", ge=0)] = 0,
    limit: Annotated[int, Query(ge=1, le=500)] = 50,
    session: Session = Depends(get_session),
):
    run = require_run(session, run_id)
    through = (
        session.scalar(
            select(func.max(RunEventRecord.sequence)).where(RunEventRecord.run_id == run_id)
        )
        or 0
    )
    if after_sequence > through:
        raise_code("invalid_cursor")
    rows = session.scalars(
        select(RunEventRecord)
        .where(
            RunEventRecord.run_id == run_id,
            RunEventRecord.sequence > after_sequence,
        )
        .order_by(RunEventRecord.sequence)
        .limit(limit + 1)
    ).all()
    next_after = rows[limit - 1].sequence if len(rows) > limit else None
    return {
        "run": run_dict(run),
        "events": [event_dict(value) for value in rows[:limit]],
        "through_sequence": through,
        "next_after_sequence": next_after,
    }


@router.get("/runs/{run_id}/events/stream")
async def stream_run_events(
    run_id: str,
    request: Request,
    last_event_id: Annotated[str | None, Header(alias="Last-Event-ID")] = None,
):
    session_factory = request.app.state.session_factory
    with session_factory() as session:
        require_run(session, run_id)
        through = (
            session.scalar(
                select(func.max(RunEventRecord.sequence)).where(RunEventRecord.run_id == run_id)
            )
            or 0
        )
        after = 0
        if last_event_id is not None:
            parts = last_event_id.split(":")
            if len(parts) != 2 or parts[0] != run_id:
                raise_code("invalid_sse_cursor")
            try:
                after = int(parts[1])
            except ValueError:
                raise_code("invalid_sse_cursor")
            if after < 0 or after > through:
                raise_code("invalid_sse_cursor")

    async def event_source():
        cursor = after
        last_heartbeat = time.monotonic()
        while True:
            if await request.is_disconnected():
                return
            with session_factory() as session:
                run = session.get(RunRecord, run_id)
                if run is None:
                    return
                rows = session.scalars(
                    select(RunEventRecord)
                    .where(
                        RunEventRecord.run_id == run_id,
                        RunEventRecord.sequence > cursor,
                    )
                    .order_by(RunEventRecord.sequence)
                    .limit(100)
                ).all()
                through_now = (
                    session.scalar(
                        select(func.max(RunEventRecord.sequence)).where(
                            RunEventRecord.run_id == run_id
                        )
                    )
                    or 0
                )
                terminal = run.status in {"completed", "failed"}
                frames = []
                for row in rows:
                    event = RunEvent.model_validate(event_dict(row)).model_dump(
                        mode="json", by_alias=True
                    )
                    frames.append(
                        (
                            row.sequence,
                            row.event_type,
                            json.dumps(event, ensure_ascii=False, separators=(",", ":")),
                        )
                    )
            for sequence, event_type, data in frames:
                cursor = sequence
                yield f"id: {run_id}:{sequence}\nevent: {event_type}\ndata: {data}\n\n"
            if terminal and cursor >= through_now:
                return
            now = time.monotonic()
            if now - last_heartbeat >= 15:
                yield ": heartbeat\n\n"
                last_heartbeat = now
            await asyncio.sleep(0.5)

    return StreamingResponse(
        event_source(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
            "Connection": "keep-alive",
        },
    )


@router.get("/providers", response_model=list[ProviderStatus])
def get_providers():
    return [
        {
            "provider": "answer_provider",
            "profile": "stage_a_mock",
            "mode": "mock",
            "registered": True,
            "selected": True,
            "available": True,
            "status_message": "已选择内置 DEMO / MOCK 适配器。",
        }
    ]

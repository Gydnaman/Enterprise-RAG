from __future__ import annotations

import uuid
from datetime import UTC, datetime

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from rag_workbench.adapters.models import RunEventRecord, RunRecord


def append_event(
    session: Session,
    run: RunRecord,
    event_type: str,
    phase: str,
    status: str,
    payload: dict,
    source_key: str | None = None,
) -> RunEventRecord:
    if run.status not in {"queued", "running"}:
        raise ValueError("terminal_run")
    safe_payload = _allowlisted_payload(event_type, payload)
    sequence = (
        session.scalar(
            select(func.max(RunEventRecord.sequence)).where(RunEventRecord.run_id == run.id)
        )
        or 0
    ) + 1
    event = RunEventRecord(
        id=str(uuid.uuid4()),
        run_id=run.id,
        sequence=sequence,
        event_type=event_type,
        phase=phase,
        status=status,
        timestamp=datetime.now(UTC),
        payload=safe_payload,
        source_event_key=source_key or f"{event_type}:{sequence}",
    )
    session.add(event)
    session.flush()
    return event


def _allowlisted_payload(event_type: str, payload: dict) -> dict:
    if event_type == "run_started":
        return {"kind": str(payload.get("kind", ""))[:32], "mode": "mock"}
    if event_type == "phase_updated":
        return {
            "phase": str(payload.get("phase", ""))[:40],
            "status": str(payload.get("status", ""))[:32],
            "summary": str(payload.get("summary", ""))[:240],
        }
    if event_type == "answer_delta":
        return {
            "messageId": str(payload.get("messageId", "")),
            "text": str(payload.get("text", ""))[:1024],
        }
    if event_type == "citation_added":
        return {
            "messageId": str(payload.get("messageId", "")),
            "revisionId": str(payload.get("revisionId", "")),
            "chunkId": str(payload.get("chunkId", "")),
            "page": payload.get("page"),
            "quote": str(payload.get("quote", ""))[:600],
        }
    if event_type == "upload_completed":
        return {
            "documentId": str(payload.get("documentId", "")),
            "revisionId": str(payload.get("revisionId", "")),
            "storedBytes": max(0, int(payload.get("storedBytes", 0))),
        }
    if event_type == "run_completed":
        result = {"resultStatus": str(payload.get("resultStatus", "completed"))[:32]}
        if payload.get("messageId"):
            result["messageId"] = str(payload["messageId"])
        return result
    if event_type == "run_failed":
        return {
            "safeErrorCode": str(payload.get("safeErrorCode", "internal_error"))[:64],
            "retryable": bool(payload.get("retryable", False)),
        }
    if event_type == "retrieval_completed":
        refs = payload.get("evidenceRefs", [])
        return {
            "evidenceCount": max(0, int(payload.get("evidenceCount", len(refs)))),
            "evidenceRefs": [
                {
                    "revisionId": str(item.get("revisionId", "")),
                    "chunkId": str(item.get("chunkId", "")),
                    "rank": int(item.get("rank", 0)),
                    "score": float(item.get("score", 0)),
                    "quote": str(item.get("quote", ""))[:600],
                }
                for item in refs[:20]
            ],
        }
    raise ValueError("event_type_not_allowed")

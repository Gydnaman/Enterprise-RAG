from __future__ import annotations

from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.orm import sessionmaker

from rag_workbench.adapters.files import LocalFileStore
from rag_workbench.adapters.models import (
    DocumentRecord,
    IdempotencyRecord,
    MessageRecord,
    RevisionRecord,
    RunRecord,
)
from rag_workbench.application.run_events import append_event


def reconcile_uploads(session_factory: sessionmaker, file_store: LocalFileStore) -> None:
    with session_factory() as session:
        records = session.scalars(
            select(IdempotencyRecord).where(
                IdempotencyRecord.operation_type == "upload",
                IdempotencyRecord.status == "pending",
            )
        ).all()
        known_stage_keys: set[str] = set()
        for record in records:
            private = dict(record.private_data)
            stage_key = private.get("stageKey", "")
            final_key = private.get("storageKey", "")
            known_stage_keys.add(stage_key)
            expected = private.get("digest")
            stage_digest = file_store.digest(stage_key, staged=True) if stage_key else None
            final_digest = file_store.digest(final_key, staged=False) if final_key else None
            if stage_digest == expected and final_digest is None:
                try:
                    file_store.finalize(stage_key, final_key)
                except OSError:
                    # Keep the idempotency record and run pending so a later
                    # startup or same-key retry can recover transient storage failures.
                    continue
                final_digest = file_store.digest(final_key, staged=False)
            document = session.get(DocumentRecord, private.get("documentId", ""))
            revision = session.get(RevisionRecord, private.get("revisionId", ""))
            run = session.get(RunRecord, private.get("runId", ""))
            if document is None or revision is None or run is None:
                record.status = "failed"
                record.safe_error_code = "storage_unavailable"
                session.commit()
                continue
            if expected and final_digest == expected:
                document.status = "uploaded_unprocessed"
                revision.status = "uploaded_unprocessed"
                record.status = "completed"
                append_event(
                    session,
                    run,
                    "upload_completed",
                    "upload",
                    "completed",
                    {
                        "documentId": document.id,
                        "revisionId": revision.id,
                        "storedBytes": document.size_bytes,
                    },
                )
                append_event(
                    session,
                    run,
                    "run_completed",
                    "upload",
                    "completed",
                    {"resultStatus": "uploaded_unprocessed"},
                )
                run.status = "completed"
                run.result_status = "uploaded_unprocessed"
                run.finished_at = datetime.now(UTC)
            else:
                document.status = "upload_failed"
                revision.status = "upload_failed"
                record.status = "failed"
                record.safe_error_code = "storage_unavailable"
                append_event(
                    session,
                    run,
                    "run_failed",
                    "upload",
                    "failed",
                    {"safeErrorCode": "storage_unavailable", "retryable": True},
                )
                run.status = "failed"
                run.safe_error_code = "storage_unavailable"
                run.finished_at = datetime.now(UTC)
            session.commit()
        for orphan in file_store.root.glob("stage_*.part"):
            key = orphan.stem
            if key not in known_stage_keys:
                orphan.unlink(missing_ok=True)


def fail_interrupted_dispatcher_runs(session_factory: sessionmaker) -> None:
    with session_factory() as session:
        runs = session.scalars(
            select(RunRecord).where(
                RunRecord.kind.in_(["answer", "demo_trace"]),
                RunRecord.status.in_(["queued", "running"]),
            )
        ).all()
        for run in runs:
            subject = dict(run.subject)
            if run.kind == "answer":
                assistant = session.get(MessageRecord, subject.get("assistantMessageId", ""))
                if assistant is not None:
                    assistant.status = "failed"
                    assistant.content = ""
                    assistant.citations = []
            append_event(
                session,
                run,
                "run_failed",
                run.kind,
                "failed",
                {"safeErrorCode": "process_interrupted", "retryable": False},
            )
            run.status = "failed"
            run.safe_error_code = "process_interrupted"
            run.finished_at = datetime.now(UTC)
        session.commit()

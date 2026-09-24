from __future__ import annotations

import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, File, Header, Query, Request, UploadFile, status
from fastapi.responses import JSONResponse
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from rag_workbench.adapters.database import get_session
from rag_workbench.adapters.models import (
    ChunkRecord,
    DocumentRecord,
    IdempotencyRecord,
    KnowledgeBaseRecord,
    RevisionRecord,
    RunRecord,
    SectionRecord,
)
from rag_workbench.adapters.upload_validation import validate_staged_file
from rag_workbench.api.routes_common import (
    new_id,
    now_utc,
    page_window,
    raise_code,
    require_document,
    require_kb,
)
from rag_workbench.api.schemas import (
    ChunkTree,
    CreateKnowledgeBaseRequest,
    Document,
    DocumentDetail,
    KnowledgeBase,
    Page,
    PendingUpload,
    ProcessResult,
    UploadResult,
)
from rag_workbench.application.idempotency import (
    check_fingerprint,
    find_record,
    fingerprint,
    operation_lock,
)
from rag_workbench.application.run_events import append_event
from rag_workbench.application.serialization import (
    document_dict,
    kb_dict,
    revision_dict,
    run_dict,
    section_dict,
)
from rag_workbench.domain.rules import normalize_display_filename, validate_idempotency_key

router = APIRouter()


@router.get("/knowledge-bases", response_model=Page[KnowledgeBase])
def list_knowledge_bases(
    page: Annotated[int, Query(ge=1)] = 1,
    page_size: Annotated[int, Query(alias="pageSize", ge=1, le=100)] = 50,
    session: Session = Depends(get_session),
):
    offset, limit = page_window(page, page_size)
    total = session.scalar(select(func.count()).select_from(KnowledgeBaseRecord)) or 0
    rows = session.scalars(
        select(KnowledgeBaseRecord)
        .order_by(KnowledgeBaseRecord.created_at.desc())
        .offset(offset)
        .limit(limit)
    ).all()
    return {
        "items": [kb_dict(value) for value in rows],
        "page": page,
        "page_size": page_size,
        "total": total,
    }


@router.post("/knowledge-bases", response_model=KnowledgeBase, status_code=status.HTTP_201_CREATED)
def create_knowledge_base(
    body: CreateKnowledgeBaseRequest, session: Session = Depends(get_session)
):
    value = KnowledgeBaseRecord(
        id=new_id(),
        name=body.name.strip(),
        description=body.description.strip() if body.description is not None else None,
    )
    session.add(value)
    session.commit()
    session.refresh(value)
    return kb_dict(value)


@router.get("/knowledge-bases/{knowledge_base_id}/documents", response_model=Page[Document])
def list_documents(
    knowledge_base_id: str,
    page: Annotated[int, Query(ge=1)] = 1,
    page_size: Annotated[int, Query(alias="pageSize", ge=1, le=100)] = 50,
    session: Session = Depends(get_session),
):
    require_kb(session, knowledge_base_id)
    offset, limit = page_window(page, page_size)
    base = select(DocumentRecord).where(DocumentRecord.knowledge_base_id == knowledge_base_id)
    total = session.scalar(select(func.count()).select_from(base.subquery())) or 0
    rows = session.scalars(
        base.order_by(DocumentRecord.created_at.desc()).offset(offset).limit(limit)
    ).all()
    return {
        "items": [document_dict(value) for value in rows],
        "page": page,
        "page_size": page_size,
        "total": total,
    }


@router.post(
    "/knowledge-bases/{knowledge_base_id}/documents",
    response_model=UploadResult,
    status_code=status.HTTP_201_CREATED,
    responses={202: {"model": PendingUpload}},
)
async def upload_document(
    knowledge_base_id: str,
    request: Request,
    idempotency_key: Annotated[
        str, Header(alias="Idempotency-Key", min_length=1, max_length=128)
    ],
    file: UploadFile = File(...),
):
    session_factory = request.app.state.session_factory
    store = request.app.state.file_store
    try:
        validate_idempotency_key(idempotency_key)
    except ValueError:
        raise_code("invalid_request")
    with session_factory() as session:
        require_kb(session, knowledge_base_id)
    try:
        stage_key, size, digest = await store.stage(
            file, request.app.state.settings.upload_max_bytes
        )
    except ValueError as exc:
        raise_code(str(exc))
    except OSError:
        raise_code("storage_unavailable")
    filename = normalize_display_filename(file.filename or "upload.txt")
    try:
        media_type = validate_staged_file(store.staged_path(stage_key), filename)
    except ValueError as exc:
        store.discard_stage(stage_key)
        raise_code(str(exc))
    key_fingerprint = fingerprint(
        {"filename": filename, "mediaType": media_type, "sizeBytes": size, "sha256": digest}
    )
    async with operation_lock("upload", knowledge_base_id, idempotency_key):
        with session_factory() as session:
            existing = find_record(session, "upload", knowledge_base_id, idempotency_key)
            if existing is not None:
                store.discard_stage(stage_key)
                try:
                    check_fingerprint(existing, key_fingerprint)
                except ValueError:
                    raise_code("idempotency_key_conflict")
                if existing.status == "failed":
                    raise_code(
                        existing.safe_error_code or "storage_unavailable",
                        existing.private_data.get("runId"),
                    )
                if existing.status == "pending":
                    try:
                        finalized = _finalize_pending_upload(session, existing, store)
                    except OSError:
                        raise_code("storage_unavailable", existing.private_data.get("runId"))
                    if not finalized:
                        return JSONResponse(
                            status_code=202,
                            content={
                                "status": "upload_pending",
                                "documentId": existing.private_data.get("documentId"),
                                "revisionId": existing.private_data.get("revisionId"),
                                "runId": existing.private_data.get("runId"),
                            },
                        )
                return _upload_result(session, existing.private_data)

            document_id, revision_id, run_id = new_id(), new_id(), new_id()
            storage_key = f"file_{uuid.uuid4().hex}"
            subject = {
                "kind": "upload",
                "knowledgeBaseId": knowledge_base_id,
                "documentId": document_id,
                "revisionId": revision_id,
            }
            document = DocumentRecord(
                id=document_id,
                knowledge_base_id=knowledge_base_id,
                filename=filename,
                media_type=media_type,
                size_bytes=size,
                is_fixture=False,
                status="upload_pending",
                current_revision_id=revision_id,
            )
            revision = RevisionRecord(
                id=revision_id,
                document_id=document_id,
                revision_number=1,
                status="upload_pending",
                storage_key=storage_key,
                content_digest=digest,
            )
            run = RunRecord(
                id=run_id, kind="upload", status="running", mode="mock", subject=subject
            )
            record = IdempotencyRecord(
                id=new_id(),
                operation_type="upload",
                owner_id=knowledge_base_id,
                key=idempotency_key,
                fingerprint=key_fingerprint,
                resource_id=document_id,
                status="pending",
                private_data={
                    "stageKey": stage_key,
                    "storageKey": storage_key,
                    "digest": digest,
                    "documentId": document_id,
                    "revisionId": revision_id,
                    "runId": run_id,
                },
            )
            try:
                session.add_all([document, revision, run, record])
                append_event(
                    session,
                    run,
                    "run_started",
                    "upload",
                    "running",
                    {"kind": "upload", "mode": "mock"},
                )
                session.commit()
            except IntegrityError:
                session.rollback()
                store.discard_stage(stage_key)
                raise_code("idempotency_key_conflict")
            try:
                store.finalize(stage_key, storage_key)
            except OSError:
                raise_code("storage_unavailable", run_id)
            try:
                finalized = _finalize_pending_upload(session, record, store)
            except Exception:
                session.rollback()
                raise_code("storage_unavailable", run_id)
            if not finalized:
                raise_code("storage_unavailable", run_id)
            return _upload_result(session, record.private_data)


def _finalize_pending_upload(session: Session, record: IdempotencyRecord, store) -> bool:
    private = dict(record.private_data)
    stage_key, storage_key, digest = (
        private.get("stageKey"),
        private.get("storageKey"),
        private.get("digest"),
    )
    if not stage_key or not storage_key or not digest:
        return False
    final_digest = store.digest(storage_key, staged=False)
    if final_digest != digest:
        if store.digest(stage_key, staged=True) != digest:
            return False
        store.finalize(stage_key, storage_key)
        final_digest = store.digest(storage_key, staged=False)
    if final_digest != digest:
        return False
    document = session.get(DocumentRecord, private["documentId"])
    revision = session.get(RevisionRecord, private["revisionId"])
    run = session.get(RunRecord, private["runId"])
    if (
        document is None
        or revision is None
        or run is None
        or run.status not in {"running", "queued"}
    ):
        return False
    document.status = revision.status = "uploaded_unprocessed"
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
    run.finished_at = now_utc()
    record.status = "completed"
    session.commit()
    return True


def _upload_result(session: Session, private: dict) -> dict:
    document = session.get(DocumentRecord, private["documentId"])
    revision = session.get(RevisionRecord, private["revisionId"])
    run = session.get(RunRecord, private["runId"])
    return {
        "document": document_dict(document),
        "revision": revision_dict(revision),
        "run": run_dict(run),
    }


@router.get("/documents/{document_id}", response_model=DocumentDetail)
def get_document(document_id: str, session: Session = Depends(get_session)):
    document = require_document(session, document_id)
    revision = session.get(RevisionRecord, document.current_revision_id)
    if revision is None:
        raise_code("resource_not_found")
    return {
        "document": document_dict(document),
        "current_revision": revision_dict(revision),
        "is_retrievable": document.is_fixture
        and document.status == "ready"
        and revision.status == "ready",
    }


@router.get("/documents/{document_id}/chunks", response_model=ChunkTree)
def get_document_chunks(
    document_id: str,
    revision_id: str | None = Query(default=None, alias="revisionId"),
    session: Session = Depends(get_session),
):
    document = require_document(session, document_id)
    revision = session.get(RevisionRecord, revision_id or document.current_revision_id)
    if revision is None or revision.document_id != document.id:
        raise_code("resource_not_found")
    section_rows = session.scalars(
        select(SectionRecord)
        .where(SectionRecord.revision_id == revision.id)
        .order_by(SectionRecord.order_number)
    ).all()
    sections = []
    for section in section_rows:
        chunks = session.scalars(
            select(ChunkRecord)
            .where(ChunkRecord.section_id == section.id)
            .order_by(ChunkRecord.order_number)
        ).all()
        sections.append(section_dict(section, chunks))
    return {"revision": revision_dict(revision), "sections": sections}


@router.post("/documents/{document_id}/process", response_model=ProcessResult, status_code=202)
async def process_document(
    document_id: str,
    request: Request,
    idempotency_key: Annotated[
        str, Header(alias="Idempotency-Key", min_length=1, max_length=128)
    ],
):
    return await _queue_demo_trace(document_id, request, idempotency_key, retry=False)


@router.post("/documents/{document_id}/retry", response_model=ProcessResult, status_code=202)
async def retry_document(
    document_id: str,
    request: Request,
    idempotency_key: Annotated[
        str, Header(alias="Idempotency-Key", min_length=1, max_length=128)
    ],
):
    return await _queue_demo_trace(document_id, request, idempotency_key, retry=True)


async def _queue_demo_trace(document_id: str, request: Request, key: str, retry: bool) -> dict:
    try:
        validate_idempotency_key(key)
    except ValueError:
        raise_code("invalid_request")
    session_factory = request.app.state.session_factory
    dispatcher = request.app.state.dispatcher
    async with operation_lock("demo_trace", document_id, key):
        with session_factory() as session:
            document = require_document(session, document_id)
            expected_fingerprint = fingerprint(
                {"documentId": document_id, "operation": "retry" if retry else "process"}
            )
            existing = find_record(session, "demo_trace", document_id, key)
            if existing is not None:
                try:
                    check_fingerprint(existing, expected_fingerprint)
                except ValueError:
                    raise_code("idempotency_key_conflict")
                run = session.get(RunRecord, existing.resource_id)
                if run is None:
                    raise_code("resource_not_found")
                return {"run": run_dict(run), "document": document_dict(document)}
            attempts = session.scalars(
                select(RunRecord).where(
                    RunRecord.kind == "demo_trace",
                    RunRecord.demo_document_id == document_id,
                )
            ).all()
            if retry:
                first = next((r for r in attempts if r.subject.get("attemptNumber") == 1), None)
                if (
                    first is None
                    or first.status != "failed"
                    or any(r.subject.get("attemptNumber") == 2 for r in attempts)
                ):
                    raise_code("invalid_state_transition")
                attempt = 2
            else:
                if (
                    document.fixture_key != "fixture-doc-handbook"
                    and document.status != "uploaded_unprocessed"
                ):
                    raise_code("invalid_state_transition")
                if any(r.subject.get("attemptNumber") == 1 for r in attempts):
                    raise_code("invalid_state_transition")
                attempt = 1
            if not await dispatcher.reserve():
                raise_code("runner_busy")
            run_id = new_id()
            run = RunRecord(
                id=run_id,
                kind="demo_trace",
                status="queued",
                mode="mock",
                demo_document_id=document.id,
                attempt_number=attempt,
                subject={
                    "kind": "demo_trace",
                    "documentId": document.id,
                    "revisionId": document.current_revision_id,
                    "attemptNumber": attempt,
                },
            )
            record = IdempotencyRecord(
                id=new_id(),
                operation_type="demo_trace",
                owner_id=document_id,
                key=key,
                fingerprint=expected_fingerprint,
                resource_id=run_id,
                status="pending",
                private_data={},
            )
            session.add_all([run, record])
            try:
                session.commit()
            except IntegrityError:
                session.rollback()
                dispatcher.release_reservation()
                raise_code("invalid_state_transition")
            dispatcher.enqueue_reserved(run_id)
            return {"run": run_dict(run), "document": document_dict(document)}

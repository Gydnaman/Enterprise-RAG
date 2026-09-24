from __future__ import annotations

from rag_workbench.adapters.models import (
    ChunkRecord,
    ConversationRecord,
    DocumentRecord,
    KnowledgeBaseRecord,
    MessageRecord,
    RevisionRecord,
    RunEventRecord,
    RunRecord,
    SectionRecord,
)


def kb_dict(value: KnowledgeBaseRecord) -> dict:
    return {
        "id": value.id,
        "name": value.name,
        "description": value.description,
        "created_at": value.created_at,
        "updated_at": value.updated_at,
    }


def document_dict(value: DocumentRecord) -> dict:
    return {
        "id": value.id,
        "knowledge_base_id": value.knowledge_base_id,
        "filename": value.filename,
        "media_type": value.media_type,
        "size_bytes": value.size_bytes,
        "is_fixture": value.is_fixture,
        "status": value.status,
        "current_revision_id": value.current_revision_id,
        "created_at": value.created_at,
    }


def revision_dict(value: RevisionRecord) -> dict:
    return {
        "id": value.id,
        "document_id": value.document_id,
        "revision_number": value.revision_number,
        "status": value.status,
        "created_at": value.created_at,
    }


def section_dict(value: SectionRecord, chunks: list[ChunkRecord]) -> dict:
    return {
        "id": value.id,
        "revision_id": value.revision_id,
        "title": value.title,
        "order": value.order_number,
        "page_start": value.page_start,
        "page_end": value.page_end,
        "heading_path": value.heading_path,
        "chunks": [chunk_dict(chunk) for chunk in chunks],
    }


def chunk_dict(value: ChunkRecord) -> dict:
    return {
        "id": value.id,
        "section_id": value.section_id,
        "order": value.order_number,
        "text": value.text,
        "page_start": value.page_start,
        "page_end": value.page_end,
        "start_offset": value.start_offset,
        "end_offset": value.end_offset,
    }


def conversation_dict(value: ConversationRecord) -> dict:
    return {
        "id": value.id,
        "knowledge_base_id": value.knowledge_base_id,
        "created_at": value.created_at,
    }


def message_dict(value: MessageRecord) -> dict:
    return {
        "id": value.id,
        "conversation_id": value.conversation_id,
        "sequence": value.sequence,
        "role": value.role,
        "status": value.status,
        "content": value.content,
        "citations": value.citations,
        "run_id": value.run_id,
        "created_at": value.created_at,
    }


def run_dict(value: RunRecord) -> dict:
    return {
        "id": value.id,
        "kind": value.kind,
        "status": value.status,
        "mode": "mock",
        "subject": value.subject,
        "created_at": value.created_at,
        "started_at": value.started_at,
        "finished_at": value.finished_at,
        "result_status": value.result_status,
        "safe_error_code": value.safe_error_code,
    }


def event_dict(value: RunEventRecord) -> dict:
    return {
        "run_id": value.run_id,
        "sequence": value.sequence,
        "event_type": value.event_type,
        "phase": value.phase,
        "status": value.status,
        "timestamp": value.timestamp,
        "payload": value.payload,
    }

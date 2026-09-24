from __future__ import annotations

from datetime import UTC, datetime

from sqlalchemy import (
    JSON,
    Boolean,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from rag_workbench.adapters.database import Base


def utcnow() -> datetime:
    return datetime.now(UTC)


class KnowledgeBaseRecord(Base):
    __tablename__ = "knowledge_bases"
    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    name: Mapped[str] = mapped_column(String(120), nullable=False)
    description: Mapped[str | None] = mapped_column(String(2000))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, onupdate=utcnow, nullable=False
    )
    documents: Mapped[list[DocumentRecord]] = relationship(back_populates="knowledge_base")


class DocumentRecord(Base):
    __tablename__ = "documents"
    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    knowledge_base_id: Mapped[str] = mapped_column(
        ForeignKey("knowledge_bases.id", ondelete="RESTRICT"), index=True
    )
    filename: Mapped[str] = mapped_column(String(255), nullable=False)
    media_type: Mapped[str] = mapped_column(String(150), nullable=False)
    size_bytes: Mapped[int] = mapped_column(Integer, nullable=False)
    is_fixture: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    status: Mapped[str] = mapped_column(String(32), nullable=False)
    current_revision_id: Mapped[str] = mapped_column(String(64), nullable=False)
    fixture_key: Mapped[str | None] = mapped_column(String(128))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, nullable=False
    )
    knowledge_base: Mapped[KnowledgeBaseRecord] = relationship(back_populates="documents")
    revisions: Mapped[list[RevisionRecord]] = relationship(back_populates="document")


class RevisionRecord(Base):
    __tablename__ = "document_revisions"
    __table_args__ = (UniqueConstraint("document_id", "revision_number"),)
    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    document_id: Mapped[str] = mapped_column(
        ForeignKey("documents.id", ondelete="RESTRICT"), index=True
    )
    revision_number: Mapped[int] = mapped_column(Integer, nullable=False)
    status: Mapped[str] = mapped_column(String(32), nullable=False)
    storage_key: Mapped[str | None] = mapped_column(String(128))
    fixture_key: Mapped[str | None] = mapped_column(String(128))
    content_digest: Mapped[str | None] = mapped_column(String(64))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, nullable=False
    )
    document: Mapped[DocumentRecord] = relationship(back_populates="revisions")
    sections: Mapped[list[SectionRecord]] = relationship(back_populates="revision")


class SectionRecord(Base):
    __tablename__ = "sections"
    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    revision_id: Mapped[str] = mapped_column(
        ForeignKey("document_revisions.id", ondelete="RESTRICT"), index=True
    )
    title: Mapped[str] = mapped_column(String(500), nullable=False)
    order_number: Mapped[int] = mapped_column(Integer, nullable=False)
    page_start: Mapped[int | None] = mapped_column(Integer)
    page_end: Mapped[int | None] = mapped_column(Integer)
    heading_path: Mapped[list[str]] = mapped_column(JSON, nullable=False)
    revision: Mapped[RevisionRecord] = relationship(back_populates="sections")
    chunks: Mapped[list[ChunkRecord]] = relationship(back_populates="section")


class ChunkRecord(Base):
    __tablename__ = "chunks"
    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    section_id: Mapped[str] = mapped_column(
        ForeignKey("sections.id", ondelete="RESTRICT"), index=True
    )
    order_number: Mapped[int] = mapped_column(Integer, nullable=False)
    text: Mapped[str] = mapped_column(Text, nullable=False)
    page_start: Mapped[int | None] = mapped_column(Integer)
    page_end: Mapped[int | None] = mapped_column(Integer)
    start_offset: Mapped[int | None] = mapped_column(Integer)
    end_offset: Mapped[int | None] = mapped_column(Integer)
    section: Mapped[SectionRecord] = relationship(back_populates="chunks")


class RunRecord(Base):
    __tablename__ = "runs"
    __table_args__ = (UniqueConstraint("demo_document_id", "attempt_number"),)
    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    kind: Mapped[str] = mapped_column(String(32), nullable=False, index=True)
    status: Mapped[str] = mapped_column(String(32), nullable=False, index=True)
    mode: Mapped[str] = mapped_column(String(16), default="mock", nullable=False)
    conversation_id: Mapped[str | None] = mapped_column(String(64), index=True)
    demo_document_id: Mapped[str | None] = mapped_column(String(64))
    attempt_number: Mapped[int | None] = mapped_column(Integer)
    subject: Mapped[dict] = mapped_column(JSON, nullable=False)
    result_status: Mapped[str | None] = mapped_column(String(32))
    safe_error_code: Mapped[str | None] = mapped_column(String(64))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, nullable=False, index=True
    )
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    events: Mapped[list[RunEventRecord]] = relationship(
        back_populates="run", order_by="RunEventRecord.sequence"
    )


class RunEventRecord(Base):
    __tablename__ = "run_events"
    __table_args__ = (
        UniqueConstraint("run_id", "sequence"),
        UniqueConstraint("run_id", "source_event_key"),
    )
    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    run_id: Mapped[str] = mapped_column(ForeignKey("runs.id", ondelete="RESTRICT"), index=True)
    sequence: Mapped[int] = mapped_column(Integer, nullable=False)
    event_type: Mapped[str] = mapped_column(String(40), nullable=False)
    phase: Mapped[str] = mapped_column(String(40), nullable=False)
    status: Mapped[str] = mapped_column(String(32), nullable=False)
    timestamp: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, nullable=False
    )
    payload: Mapped[dict] = mapped_column(JSON, nullable=False)
    source_event_key: Mapped[str] = mapped_column(String(128), nullable=False)
    run: Mapped[RunRecord] = relationship(back_populates="events")


class IdempotencyRecord(Base):
    __tablename__ = "idempotency_records"
    __table_args__ = (UniqueConstraint("operation_type", "owner_id", "key"),)
    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    operation_type: Mapped[str] = mapped_column(String(32), nullable=False)
    owner_id: Mapped[str] = mapped_column(String(64), nullable=False)
    key: Mapped[str] = mapped_column(String(128), nullable=False)
    fingerprint: Mapped[str] = mapped_column(String(64), nullable=False)
    resource_id: Mapped[str | None] = mapped_column(String(64))
    status: Mapped[str] = mapped_column(String(32), nullable=False)
    safe_error_code: Mapped[str | None] = mapped_column(String(64))
    private_data: Mapped[dict] = mapped_column(JSON, default=dict, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, nullable=False
    )


class ConversationRecord(Base):
    __tablename__ = "conversations"
    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    knowledge_base_id: Mapped[str] = mapped_column(
        ForeignKey("knowledge_bases.id", ondelete="RESTRICT"), index=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, nullable=False
    )
    messages: Mapped[list[MessageRecord]] = relationship(
        back_populates="conversation", order_by="MessageRecord.sequence"
    )


class MessageRecord(Base):
    __tablename__ = "messages"
    __table_args__ = (UniqueConstraint("conversation_id", "sequence"),)
    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    conversation_id: Mapped[str] = mapped_column(
        ForeignKey("conversations.id", ondelete="RESTRICT"), index=True
    )
    sequence: Mapped[int] = mapped_column(Integer, nullable=False)
    role: Mapped[str] = mapped_column(String(16), nullable=False)
    status: Mapped[str] = mapped_column(String(16), nullable=False)
    content: Mapped[str] = mapped_column(Text, nullable=False, default="")
    citations: Mapped[list[dict]] = mapped_column(JSON, default=list, nullable=False)
    run_id: Mapped[str | None] = mapped_column(String(64))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, nullable=False
    )
    conversation: Mapped[ConversationRecord] = relationship(back_populates="messages")


Index(
    "uq_active_answer_conversation",
    RunRecord.conversation_id,
    unique=True,
    sqlite_where=(RunRecord.kind == "answer") & (RunRecord.status.in_(["queued", "running"])),
    postgresql_where=(RunRecord.kind == "answer") & (RunRecord.status.in_(["queued", "running"])),
)

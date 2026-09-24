"""Stage A schema baseline.

Revision ID: 0001_stage_a
Revises:
"""
from __future__ import annotations

from alembic import op
import sqlalchemy as sa


revision = "0001_stage_a"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Keep this historical baseline explicit: later ORM changes must use a new
    # revision instead of changing the schema created by this one.
    op.create_table(
        "knowledge_bases",
        sa.Column("id", sa.String(length=64), nullable=False),
        sa.Column("name", sa.String(length=120), nullable=False),
        sa.Column("description", sa.String(length=2000), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id", name="pk_knowledge_bases"),
    )
    op.create_table(
        "documents",
        sa.Column("id", sa.String(length=64), nullable=False),
        sa.Column("knowledge_base_id", sa.String(length=64), nullable=False),
        sa.Column("filename", sa.String(length=255), nullable=False),
        sa.Column("media_type", sa.String(length=150), nullable=False),
        sa.Column("size_bytes", sa.Integer(), nullable=False),
        sa.Column("is_fixture", sa.Boolean(), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("current_revision_id", sa.String(length=64), nullable=False),
        sa.Column("fixture_key", sa.String(length=128), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["knowledge_base_id"], ["knowledge_bases.id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id", name="pk_documents"),
    )
    op.create_index("ix_documents_knowledge_base_id", "documents", ["knowledge_base_id"])
    op.create_table(
        "document_revisions",
        sa.Column("id", sa.String(length=64), nullable=False),
        sa.Column("document_id", sa.String(length=64), nullable=False),
        sa.Column("revision_number", sa.Integer(), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("storage_key", sa.String(length=128), nullable=True),
        sa.Column("fixture_key", sa.String(length=128), nullable=True),
        sa.Column("content_digest", sa.String(length=64), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["document_id"], ["documents.id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id", name="pk_document_revisions"),
        sa.UniqueConstraint("document_id", "revision_number", name="uq_document_revisions_document_number"),
    )
    op.create_index("ix_document_revisions_document_id", "document_revisions", ["document_id"])
    op.create_table(
        "sections",
        sa.Column("id", sa.String(length=64), nullable=False),
        sa.Column("revision_id", sa.String(length=64), nullable=False),
        sa.Column("title", sa.String(length=500), nullable=False),
        sa.Column("order_number", sa.Integer(), nullable=False),
        sa.Column("page_start", sa.Integer(), nullable=True),
        sa.Column("page_end", sa.Integer(), nullable=True),
        sa.Column("heading_path", sa.JSON(), nullable=False),
        sa.ForeignKeyConstraint(["revision_id"], ["document_revisions.id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id", name="pk_sections"),
    )
    op.create_index("ix_sections_revision_id", "sections", ["revision_id"])
    op.create_table(
        "chunks",
        sa.Column("id", sa.String(length=64), nullable=False),
        sa.Column("section_id", sa.String(length=64), nullable=False),
        sa.Column("order_number", sa.Integer(), nullable=False),
        sa.Column("text", sa.Text(), nullable=False),
        sa.Column("page_start", sa.Integer(), nullable=True),
        sa.Column("page_end", sa.Integer(), nullable=True),
        sa.Column("start_offset", sa.Integer(), nullable=True),
        sa.Column("end_offset", sa.Integer(), nullable=True),
        sa.ForeignKeyConstraint(["section_id"], ["sections.id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id", name="pk_chunks"),
    )
    op.create_index("ix_chunks_section_id", "chunks", ["section_id"])
    op.create_table(
        "runs",
        sa.Column("id", sa.String(length=64), nullable=False),
        sa.Column("kind", sa.String(length=32), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("mode", sa.String(length=16), nullable=False),
        sa.Column("conversation_id", sa.String(length=64), nullable=True),
        sa.Column("demo_document_id", sa.String(length=64), nullable=True),
        sa.Column("attempt_number", sa.Integer(), nullable=True),
        sa.Column("subject", sa.JSON(), nullable=False),
        sa.Column("result_status", sa.String(length=32), nullable=True),
        sa.Column("safe_error_code", sa.String(length=64), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("finished_at", sa.DateTime(timezone=True), nullable=True),
        sa.PrimaryKeyConstraint("id", name="pk_runs"),
        sa.UniqueConstraint("demo_document_id", "attempt_number", name="uq_runs_demo_document_attempt"),
    )
    op.create_index("ix_runs_kind", "runs", ["kind"])
    op.create_index("ix_runs_status", "runs", ["status"])
    op.create_index("ix_runs_conversation_id", "runs", ["conversation_id"])
    op.create_index("ix_runs_created_at", "runs", ["created_at"])
    op.create_index(
        "uq_active_answer_conversation",
        "runs",
        ["conversation_id"],
        unique=True,
        sqlite_where=sa.text("kind = 'answer' AND status IN ('queued', 'running')"),
        postgresql_where=sa.text("kind = 'answer' AND status IN ('queued', 'running')"),
    )
    op.create_table(
        "run_events",
        sa.Column("id", sa.String(length=64), nullable=False),
        sa.Column("run_id", sa.String(length=64), nullable=False),
        sa.Column("sequence", sa.Integer(), nullable=False),
        sa.Column("event_type", sa.String(length=40), nullable=False),
        sa.Column("phase", sa.String(length=40), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("timestamp", sa.DateTime(timezone=True), nullable=False),
        sa.Column("payload", sa.JSON(), nullable=False),
        sa.Column("source_event_key", sa.String(length=128), nullable=False),
        sa.ForeignKeyConstraint(["run_id"], ["runs.id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id", name="pk_run_events"),
        sa.UniqueConstraint("run_id", "sequence", name="uq_run_events_run_sequence"),
        sa.UniqueConstraint("run_id", "source_event_key", name="uq_run_events_run_source_key"),
    )
    op.create_index("ix_run_events_run_id", "run_events", ["run_id"])
    op.create_table(
        "idempotency_records",
        sa.Column("id", sa.String(length=64), nullable=False),
        sa.Column("operation_type", sa.String(length=32), nullable=False),
        sa.Column("owner_id", sa.String(length=64), nullable=False),
        sa.Column("key", sa.String(length=128), nullable=False),
        sa.Column("fingerprint", sa.String(length=64), nullable=False),
        sa.Column("resource_id", sa.String(length=64), nullable=True),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("safe_error_code", sa.String(length=64), nullable=True),
        sa.Column("private_data", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id", name="pk_idempotency_records"),
        sa.UniqueConstraint("operation_type", "owner_id", "key", name="uq_idempotency_owner_operation_key"),
    )
    op.create_table(
        "conversations",
        sa.Column("id", sa.String(length=64), nullable=False),
        sa.Column("knowledge_base_id", sa.String(length=64), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["knowledge_base_id"], ["knowledge_bases.id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id", name="pk_conversations"),
    )
    op.create_index("ix_conversations_knowledge_base_id", "conversations", ["knowledge_base_id"])
    op.create_table(
        "messages",
        sa.Column("id", sa.String(length=64), nullable=False),
        sa.Column("conversation_id", sa.String(length=64), nullable=False),
        sa.Column("sequence", sa.Integer(), nullable=False),
        sa.Column("role", sa.String(length=16), nullable=False),
        sa.Column("status", sa.String(length=16), nullable=False),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column("citations", sa.JSON(), nullable=False),
        sa.Column("run_id", sa.String(length=64), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["conversation_id"], ["conversations.id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id", name="pk_messages"),
        sa.UniqueConstraint("conversation_id", "sequence", name="uq_messages_conversation_sequence"),
    )
    op.create_index("ix_messages_conversation_id", "messages", ["conversation_id"])


def downgrade() -> None:
    op.drop_index("ix_messages_conversation_id", table_name="messages")
    op.drop_table("messages")
    op.drop_index("ix_conversations_knowledge_base_id", table_name="conversations")
    op.drop_table("conversations")
    op.drop_table("idempotency_records")
    op.drop_index("ix_run_events_run_id", table_name="run_events")
    op.drop_table("run_events")
    op.drop_index("uq_active_answer_conversation", table_name="runs")
    op.drop_index("ix_runs_created_at", table_name="runs")
    op.drop_index("ix_runs_conversation_id", table_name="runs")
    op.drop_index("ix_runs_status", table_name="runs")
    op.drop_index("ix_runs_kind", table_name="runs")
    op.drop_table("runs")
    op.drop_index("ix_chunks_section_id", table_name="chunks")
    op.drop_table("chunks")
    op.drop_index("ix_sections_revision_id", table_name="sections")
    op.drop_table("sections")
    op.drop_index("ix_document_revisions_document_id", table_name="document_revisions")
    op.drop_table("document_revisions")
    op.drop_index("ix_documents_knowledge_base_id", table_name="documents")
    op.drop_table("documents")
    op.drop_table("knowledge_bases")

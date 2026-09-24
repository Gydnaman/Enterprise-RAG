from __future__ import annotations

from datetime import UTC, datetime
from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field, StringConstraints


def camel_case(value: str) -> str:
    first, *rest = value.split("_")
    return first + "".join(word[:1].upper() + word[1:] for word in rest)


class ApiModel(BaseModel):
    model_config = ConfigDict(
        alias_generator=camel_case,
        populate_by_name=True,
        serialize_by_alias=True,
        json_encoders={
            datetime: lambda value: value.astimezone(UTC).isoformat().replace("+00:00", "Z")
        },
    )


class KnowledgeBase(ApiModel):
    id: str
    name: str
    description: str | None
    created_at: datetime
    updated_at: datetime


class Document(ApiModel):
    id: str
    knowledge_base_id: str
    filename: str
    media_type: str
    size_bytes: int
    is_fixture: bool
    status: Literal["upload_pending", "ready", "uploaded_unprocessed", "upload_failed"]
    current_revision_id: str
    created_at: datetime


class DocumentRevision(ApiModel):
    id: str
    document_id: str
    revision_number: int
    status: Literal["upload_pending", "ready", "uploaded_unprocessed", "upload_failed"]
    created_at: datetime


class DocumentDetail(ApiModel):
    document: Document
    current_revision: DocumentRevision
    is_retrievable: bool


class Chunk(ApiModel):
    id: str
    section_id: str
    order: int
    text: str
    page_start: int | None
    page_end: int | None
    start_offset: int | None
    end_offset: int | None


class SectionWithChunks(ApiModel):
    id: str
    revision_id: str
    title: str
    order: int
    page_start: int | None
    page_end: int | None
    heading_path: list[str]
    chunks: list[Chunk]


class ChunkTree(ApiModel):
    revision: DocumentRevision
    sections: list[SectionWithChunks]


class Evidence(ApiModel):
    revision_id: str
    chunk_id: str
    document_id: str
    filename: str
    page: int | None
    heading_path: list[str]
    snippet: str
    score: float
    rank: int
    mode: Literal["mock"]


class Citation(ApiModel):
    revision_id: str
    chunk_id: str
    page: int | None
    quote: str


class Conversation(ApiModel):
    id: str
    knowledge_base_id: str
    created_at: datetime


class Message(ApiModel):
    id: str
    conversation_id: str
    sequence: int
    role: Literal["user", "assistant"]
    status: Literal["queued", "streaming", "completed", "failed"]
    content: str
    citations: list[Citation]
    run_id: str | None
    created_at: datetime


class ConversationDetail(ApiModel):
    conversation: Conversation
    messages: list[Message]
    active_run_id: str | None


class UploadSubject(ApiModel):
    kind: Literal["upload"]
    knowledge_base_id: str
    document_id: str
    revision_id: str


class DemoTraceSubject(ApiModel):
    kind: Literal["demo_trace"]
    document_id: str
    revision_id: str
    attempt_number: int


class RetrievalSubject(ApiModel):
    kind: Literal["retrieval"]
    knowledge_base_id: str


class AnswerSubject(ApiModel):
    kind: Literal["answer"]
    knowledge_base_id: str
    conversation_id: str
    user_message_id: str
    assistant_message_id: str


RunSubject = Annotated[
    UploadSubject | DemoTraceSubject | RetrievalSubject | AnswerSubject, Field(discriminator="kind")
]


class Run(ApiModel):
    id: str
    kind: Literal["upload", "demo_trace", "retrieval", "answer"]
    status: Literal["queued", "running", "completed", "failed"]
    mode: Literal["mock"]
    subject: RunSubject
    created_at: datetime
    started_at: datetime | None
    finished_at: datetime | None
    result_status: str | None
    safe_error_code: str | None


class RunEvent(ApiModel):
    run_id: str
    sequence: int
    event_type: str
    phase: str
    status: str
    timestamp: datetime
    payload: dict


class RunSnapshot(ApiModel):
    run: Run
    events: list[RunEvent]
    through_sequence: int
    next_after_sequence: int | None


class ProviderStatus(ApiModel):
    provider: str
    profile: str
    mode: Literal["mock"]
    registered: bool
    selected: bool
    available: bool
    status_message: str | None


class Page[T](ApiModel):
    items: list[T]
    page: int
    page_size: int
    total: int


class Problem(ApiModel):
    type: str
    title: str
    status: int
    detail: str
    code: str
    request_id: str
    retryable: bool
    run_id: str | None


class CreateKnowledgeBaseRequest(ApiModel):
    name: Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=120)]
    description: (
        Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=2000)]
        | None
    ) = None


class CreateConversationRequest(ApiModel):
    knowledge_base_id: str


class SendMessageRequest(ApiModel):
    question: Annotated[
        str, StringConstraints(strip_whitespace=True, min_length=1, max_length=4000)
    ]
    top_k: int = Field(default=5, ge=1, le=20)


class RetrievalDebugRequest(ApiModel):
    knowledge_base_id: str
    query: Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=4000)]
    document_ids: list[str] | None = None
    top_k: int = Field(default=5, ge=1, le=20)


class PendingUpload(ApiModel):
    status: Literal["upload_pending"]
    document_id: str
    revision_id: str
    run_id: str


class UploadResult(ApiModel):
    document: Document
    revision: DocumentRevision
    run: Run


class ProcessResult(ApiModel):
    run: Run
    document: Document


class RetrievalDebugResult(ApiModel):
    run_id: str
    mode: Literal["mock"]
    query: str
    evidence: list[Evidence]


class SendMessageResult(ApiModel):
    user_message: Message
    assistant_message: Message
    run: Run

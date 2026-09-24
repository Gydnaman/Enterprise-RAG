from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

RunKind = Literal["upload", "demo_trace", "retrieval", "answer"]
RunStatus = Literal["queued", "running", "completed", "failed"]
DocumentStatus = Literal["upload_pending", "ready", "uploaded_unprocessed", "upload_failed"]


@dataclass(frozen=True)
class EvidenceRef:
    revision_id: str
    chunk_id: str
    rank: int
    score: float
    quote: str


@dataclass(frozen=True)
class AnswerDelta:
    text: str


ABSTENTION_TEXT = "当前知识库中没有找到可引用的资料。"

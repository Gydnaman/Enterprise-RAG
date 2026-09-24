from __future__ import annotations

from collections.abc import AsyncIterator, BinaryIO, Sequence
from typing import Protocol

from rag_workbench.domain.types import AnswerDelta


class FileStore(Protocol):
    def open(self, storage_key: str) -> BinaryIO: ...

    def stage(self, chunks: AsyncIterator[bytes]) -> tuple[str, int, str]: ...

    def finalize(self, staged_key: str, storage_key: str) -> None: ...


class KnowledgeRetriever(Protocol):
    def retrieve(
        self, knowledge_base_id: str, query: str, document_ids: Sequence[str], top_k: int
    ) -> list[dict]: ...


class AnswerProvider(Protocol):
    async def stream(
        self, question: str, evidence: Sequence[dict], history: Sequence[dict]
    ) -> AsyncIterator[AnswerDelta]: ...


class DocumentParser(Protocol):
    def parse(self, stream: BinaryIO, revision_metadata: dict) -> dict: ...


class OCRProvider(Protocol):
    def extract(self, file: BinaryIO) -> dict: ...


class Chunker(Protocol):
    def split(self, parsed_document: dict, policy: dict) -> list[dict]: ...


class EmbeddingProvider(Protocol):
    def embed(self, texts: Sequence[str]) -> list[list[float]]: ...


class VectorStore(Protocol):
    def upsert(self, revision_id: str, vectors: Sequence[list[float]]) -> None: ...

    def delete(self, revision_id: str) -> None: ...

    def search(self, vector: Sequence[float], top_k: int) -> list[dict]: ...


class KeywordRetriever(Protocol):
    def search(self, query: str, filters: dict, top_k: int) -> list[dict]: ...

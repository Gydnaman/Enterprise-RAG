from __future__ import annotations

import json
import re
from pathlib import Path

from sqlalchemy import select
from sqlalchemy.orm import Session

from rag_workbench.adapters.models import (
    ChunkRecord,
    DocumentRecord,
    KnowledgeBaseRecord,
    RevisionRecord,
    SectionRecord,
)

FIXTURE_PATH = Path(__file__).parents[1] / "fixtures" / "demo_corpus.json"
FIXTURES = json.loads(FIXTURE_PATH.read_text(encoding="utf-8"))


def seed_fixtures(session: Session) -> None:
    knowledge_data = FIXTURES["knowledgeBase"]
    knowledge_base = session.get(KnowledgeBaseRecord, knowledge_data["id"])
    if knowledge_base is None:
        knowledge_base = KnowledgeBaseRecord(
            **{
                "id": knowledge_data["id"],
                "name": knowledge_data["name"],
                "description": knowledge_data["description"],
            }
        )
        session.add(knowledge_base)
        session.flush()
    for document_data in FIXTURES["documents"]:
        if session.get(DocumentRecord, document_data["id"]) is not None:
            continue
        document = DocumentRecord(
            id=document_data["id"],
            knowledge_base_id=knowledge_base.id,
            filename=document_data["filename"],
            media_type=document_data["mediaType"],
            size_bytes=sum(
                len(chunk["text"].encode("utf-8"))
                for section in document_data["sections"]
                for chunk in section["chunks"]
            ),
            is_fixture=True,
            status="ready",
            current_revision_id=document_data["revisionId"],
            fixture_key=document_data["id"],
        )
        revision = RevisionRecord(
            id=document_data["revisionId"],
            document_id=document.id,
            revision_number=document_data["revisionNumber"],
            status="ready",
            fixture_key=document_data["id"],
        )
        session.add_all([document, revision])
        for section_data in document_data["sections"]:
            section = SectionRecord(
                id=section_data["id"],
                revision_id=revision.id,
                title=section_data["title"],
                order_number=section_data["order"],
                page_start=section_data["pageStart"],
                page_end=section_data["pageEnd"],
                heading_path=section_data["headingPath"],
            )
            session.add(section)
            for chunk_data in section_data["chunks"]:
                session.add(
                    ChunkRecord(
                        id=chunk_data["id"],
                        section_id=section.id,
                        order_number=chunk_data["order"],
                        text=chunk_data["text"],
                        page_start=chunk_data["pageStart"],
                        page_end=chunk_data["pageEnd"],
                        start_offset=chunk_data["startOffset"],
                        end_offset=chunk_data["endOffset"],
                    )
                )
    session.commit()


class MockKnowledgeRetriever:
    def __init__(self, session: Session):
        self.session = session

    def retrieve(
        self, knowledge_base_id: str, query: str, document_ids: list[str] | None, top_k: int
    ) -> list[dict]:
        statement = (
            select(ChunkRecord, SectionRecord, RevisionRecord, DocumentRecord)
            .join(SectionRecord, ChunkRecord.section_id == SectionRecord.id)
            .join(RevisionRecord, SectionRecord.revision_id == RevisionRecord.id)
            .join(DocumentRecord, RevisionRecord.document_id == DocumentRecord.id)
            .where(
                DocumentRecord.knowledge_base_id == knowledge_base_id,
                DocumentRecord.is_fixture.is_(True),
                DocumentRecord.status == "ready",
                RevisionRecord.status == "ready",
            )
        )
        if document_ids:
            statement = statement.where(DocumentRecord.id.in_(document_ids))
        rows = self.session.execute(statement).all()
        query_tokens = _tokens(query)
        candidates: list[
            tuple[float, ChunkRecord, SectionRecord, RevisionRecord, DocumentRecord]
        ] = []
        for chunk, section, revision, document in rows:
            chunk_tokens = _tokens(chunk.text)
            overlap = len(query_tokens & chunk_tokens)
            phrase = query.strip().casefold() in chunk.text.casefold()
            if not overlap and not phrase:
                continue
            score = min(0.99, 0.56 + overlap * 0.07 + (0.17 if phrase else 0.0))
            candidates.append((score, chunk, section, revision, document))
        candidates.sort(key=lambda row: (-row[0], row[1].id))
        result = []
        for rank, (score, chunk, section, revision, document) in enumerate(
            candidates[:top_k], start=1
        ):
            result.append(
                {
                    "revision_id": revision.id,
                    "chunk_id": chunk.id,
                    "document_id": document.id,
                    "filename": document.filename,
                    "page": chunk.page_start,
                    "heading_path": section.heading_path,
                    "snippet": chunk.text[:600],
                    "score": round(score, 4),
                    "rank": rank,
                    "mode": "mock",
                }
            )
        return result


def _tokens(value: str) -> set[str]:
    parts = re.findall(r"[a-z0-9]{2,}|[\u3400-\u9fff]{2,}", value.casefold())
    tokens: set[str] = set(parts)
    for part in parts:
        if re.fullmatch(r"[\u3400-\u9fff]+", part):
            tokens.update(part[index : index + 2] for index in range(len(part) - 1))
    return tokens

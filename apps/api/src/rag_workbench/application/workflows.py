from __future__ import annotations

import asyncio
from datetime import UTC, datetime
from typing import TypedDict

from langgraph.graph import END, START, StateGraph
from sqlalchemy.orm import sessionmaker

from rag_workbench.adapters.database import SessionFactory
from rag_workbench.adapters.fixtures import MockKnowledgeRetriever
from rag_workbench.adapters.mock_answer import MockAnswerProvider
from rag_workbench.adapters.models import (
    ConversationRecord,
    MessageRecord,
    RunRecord,
)
from rag_workbench.application.run_events import append_event
from rag_workbench.domain.types import ABSTENTION_TEXT


class AnswerState(TypedDict, total=False):
    run_id: str
    conversation_id: str
    question: str
    top_k: int
    evidence: list[dict]
    answer: str


async def run_demo_trace(session_factory: sessionmaker, run_id: str) -> None:
    with session_factory() as session:
        run = session.get(RunRecord, run_id)
        if run is None or run.status != "queued":
            return
        run.status = "running"
        run.started_at = datetime.now(UTC)
        append_event(
            session, run, "run_started", "demo_trace", "running", {"kind": run.kind, "mode": "mock"}
        )
        append_event(
            session,
            run,
            "phase_updated",
            "demo_trace",
            "running",
            {
                "phase": "demo_trace",
                "status": "running",
                "summary": "正在演示 metadata-only 处理轨迹。",
            },
        )
        session.commit()
        attempt = int(run.subject.get("attemptNumber", 1))
        if attempt == 1:
            append_event(
                session,
                run,
                "run_failed",
                "demo_trace",
                "failed",
                {"safeErrorCode": "demo_transient_error", "retryable": True},
            )
            run.status = "failed"
            run.safe_error_code = "demo_transient_error"
            run.finished_at = datetime.now(UTC)
        else:
            append_event(
                session,
                run,
                "phase_updated",
                "demo_trace",
                "completed",
                {
                    "phase": "demo_trace",
                    "status": "completed",
                    "summary": "模拟轨迹已结束；文档仍未解析。",
                },
            )
            append_event(
                session,
                run,
                "run_completed",
                "demo_trace",
                "completed",
                {"resultStatus": "demo_succeeded"},
            )
            run.status = "completed"
            run.result_status = "demo_succeeded"
            run.finished_at = datetime.now(UTC)
        session.commit()


def _build_answer_graph():
    async def retrieve_node(state: AnswerState) -> dict:
        with SessionFactory() as session:
            conversation = session.get(ConversationRecord, state["conversation_id"])
            if conversation is None:
                return {"evidence": []}
            evidence = MockKnowledgeRetriever(session).retrieve(
                conversation.knowledge_base_id, state["question"], [], state["top_k"]
            )
            return {"evidence": evidence}

    async def answer_node(state: AnswerState) -> dict:
        pieces = []
        async for delta in MockAnswerProvider().stream(
            state["question"], state.get("evidence", []), []
        ):
            pieces.append(delta.text)
        return {"answer": "".join(pieces)}

    graph = StateGraph(AnswerState)
    graph.add_node("retrieve", retrieve_node)
    graph.add_node("answer", answer_node)
    graph.add_edge(START, "retrieve")
    graph.add_edge("retrieve", "answer")
    graph.add_edge("answer", END)
    return graph.compile()


_ANSWER_GRAPH = _build_answer_graph()


async def run_answer(session_factory: sessionmaker, run_id: str) -> None:
    with session_factory() as session:
        run = session.get(RunRecord, run_id)
        if run is None or run.status != "queued":
            return
        run.status = "running"
        run.started_at = datetime.now(UTC)
        append_event(
            session, run, "run_started", "answer", "running", {"kind": run.kind, "mode": "mock"}
        )
        append_event(
            session,
            run,
            "phase_updated",
            "retrieval",
            "running",
            {
                "phase": "retrieval",
                "status": "running",
                "summary": "正在从只读 fixture 中查找演示证据。",
            },
        )
        subject = dict(run.subject)
        assistant = session.get(MessageRecord, subject["assistantMessageId"])
        user = session.get(MessageRecord, subject["userMessageId"])
        if assistant is None or user is None:
            _fail_answer(session, run, "internal_error")
            return
        initial = {
            "run_id": run.id,
            "conversation_id": subject["conversationId"],
            "question": user.content,
            "top_k": int(run.subject.get("topK", 5)),
        }
        session.commit()
    try:
        result = await _ANSWER_GRAPH.ainvoke(initial)
        evidence = result.get("evidence", [])
        answer = result.get("answer", ABSTENTION_TEXT)
        async with asyncio.timeout(30):
            with session_factory() as session:
                run = session.get(RunRecord, run_id)
                assistant = session.get(MessageRecord, subject["assistantMessageId"])
                if run is None or assistant is None or run.status != "running":
                    return
                run.started_at = run.started_at or datetime.now(UTC)
                assistant.status = "streaming"
                append_event(
                    session,
                    run,
                    "phase_updated",
                    "retrieval",
                    "completed",
                    {
                        "phase": "retrieval",
                        "status": "completed",
                        "summary": f"找到 {len(evidence)} 条 DEMO Evidence。",
                    },
                )
                for offset in range(0, min(len(answer), 20_000), 80):
                    delta = answer[offset : offset + 80]
                    assistant.content += delta
                    append_event(
                        session,
                        run,
                        "answer_delta",
                        "answer",
                        "streaming",
                        {"messageId": assistant.id, "text": delta},
                    )
                    session.commit()
                citations = []
                # MockAnswerProvider currently grounds its answer in evidence[0] only.
                # Persist exactly the evidence used by that answer as citations.
                for item in evidence[:1]:
                    citation = {
                        "revision_id": item["revision_id"],
                        "chunk_id": item["chunk_id"],
                        "page": item["page"],
                        "quote": item["snippet"][:600],
                    }
                    citations.append(citation)
                    append_event(
                        session,
                        run,
                        "citation_added",
                        "citation",
                        "completed",
                        {
                            "messageId": assistant.id,
                            "revisionId": citation["revision_id"],
                            "chunkId": citation["chunk_id"],
                            "page": citation["page"],
                            "quote": citation["quote"],
                        },
                    )
                assistant.citations = citations
                assistant.status = "completed"
                run.result_status = "completed" if evidence else "abstained"
                append_event(
                    session,
                    run,
                    "run_completed",
                    "answer",
                    "completed",
                    {"resultStatus": run.result_status, "messageId": assistant.id},
                )
                run.status = "completed"
                run.finished_at = datetime.now(UTC)
                session.commit()
    except Exception:
        with session_factory() as session:
            run = session.get(RunRecord, run_id)
            if run is not None and run.status in {"queued", "running"}:
                _fail_answer(session, run, "internal_error")


def _fail_answer(session, run: RunRecord, code: str) -> None:
    subject = dict(run.subject)
    assistant = session.get(MessageRecord, subject.get("assistantMessageId", ""))
    if assistant is not None:
        assistant.status = "failed"
        assistant.content = ""
        assistant.citations = []
    append_event(
        session, run, "run_failed", "answer", "failed", {"safeErrorCode": code, "retryable": False}
    )
    run.status = "failed"
    run.safe_error_code = code
    run.finished_at = datetime.now(UTC)
    session.commit()

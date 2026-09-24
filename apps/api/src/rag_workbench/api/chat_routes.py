from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, Header, Request
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from rag_workbench.adapters.database import get_session
from rag_workbench.adapters.models import (
    ConversationRecord,
    IdempotencyRecord,
    MessageRecord,
    RunRecord,
)
from rag_workbench.api.routes_common import (
    new_id,
    raise_code,
    require_conversation,
    require_kb,
)
from rag_workbench.api.schemas import (
    Conversation as ConversationDto,
)
from rag_workbench.api.schemas import (
    ConversationDetail,
    CreateConversationRequest,
    SendMessageRequest,
    SendMessageResult,
)
from rag_workbench.application.idempotency import (
    check_fingerprint,
    find_record,
    fingerprint,
    operation_lock,
)
from rag_workbench.application.serialization import conversation_dict, message_dict, run_dict
from rag_workbench.domain.rules import validate_idempotency_key

router = APIRouter()


@router.post("/chat/sessions", response_model=ConversationDto, status_code=201)
def create_conversation(body: CreateConversationRequest, session: Session = Depends(get_session)):
    require_kb(session, body.knowledge_base_id)
    conversation = ConversationRecord(id=new_id(), knowledge_base_id=body.knowledge_base_id)
    session.add(conversation)
    session.commit()
    session.refresh(conversation)
    return conversation_dict(conversation)


@router.get("/chat/sessions/{conversation_id}", response_model=ConversationDetail)
def get_conversation(conversation_id: str, session: Session = Depends(get_session)):
    conversation = require_conversation(session, conversation_id)
    messages = session.scalars(
        select(MessageRecord)
        .where(MessageRecord.conversation_id == conversation_id)
        .order_by(MessageRecord.sequence)
    ).all()
    active = session.scalar(
        select(RunRecord)
        .where(
            RunRecord.conversation_id == conversation_id,
            RunRecord.kind == "answer",
            RunRecord.status.in_(["queued", "running"]),
        )
        .order_by(RunRecord.created_at.desc())
    )
    return {
        "conversation": conversation_dict(conversation),
        "messages": [message_dict(message) for message in messages],
        "active_run_id": active.id if active else None,
    }


@router.post(
    "/chat/sessions/{conversation_id}/messages", response_model=SendMessageResult, status_code=202
)
async def send_message(
    conversation_id: str,
    body: SendMessageRequest,
    request: Request,
    idempotency_key: Annotated[str, Header(alias="Idempotency-Key", min_length=1, max_length=128)],
    session: Session = Depends(get_session),
):
    try:
        validate_idempotency_key(idempotency_key)
    except ValueError:
        raise_code("invalid_request")
    conversation = require_conversation(session, conversation_id)
    operation_fingerprint = fingerprint({"question": body.question.strip(), "topK": body.top_k})
    async with operation_lock("answer", conversation_id, idempotency_key):
        existing = find_record(session, "answer", conversation_id, idempotency_key)
        if existing is not None:
            try:
                check_fingerprint(existing, operation_fingerprint)
            except ValueError:
                raise_code("idempotency_key_conflict")
            run = session.get(RunRecord, existing.resource_id)
            private = existing.private_data
            user_message = session.get(MessageRecord, private.get("userMessageId", ""))
            assistant_message = session.get(MessageRecord, private.get("assistantMessageId", ""))
            if not run or not user_message or not assistant_message:
                raise_code("resource_not_found")
            return {
                "userMessage": message_dict(user_message),
                "assistantMessage": message_dict(assistant_message),
                "run": run_dict(run),
            }

        busy = session.scalar(
            select(RunRecord).where(
                RunRecord.conversation_id == conversation_id,
                RunRecord.kind == "answer",
                RunRecord.status.in_(["queued", "running"]),
            )
        )
        if busy is not None:
            raise_code("conversation_busy")
        dispatcher = request.app.state.dispatcher
        if not await dispatcher.reserve():
            raise_code("runner_busy")

        max_sequence = (
            session.scalar(
                select(func.max(MessageRecord.sequence)).where(
                    MessageRecord.conversation_id == conversation_id
                )
            )
            or 0
        )
        user_message = MessageRecord(
            id=new_id(),
            conversation_id=conversation_id,
            sequence=max_sequence + 1,
            role="user",
            status="completed",
            content=body.question.strip(),
            citations=[],
            run_id=None,
        )
        assistant_message = MessageRecord(
            id=new_id(),
            conversation_id=conversation_id,
            sequence=max_sequence + 2,
            role="assistant",
            status="queued",
            content="",
            citations=[],
            run_id=None,
        )
        run_id = new_id()
        assistant_message.run_id = run_id
        run = RunRecord(
            id=run_id,
            kind="answer",
            status="queued",
            mode="mock",
            conversation_id=conversation_id,
            subject={
                "kind": "answer",
                "knowledgeBaseId": conversation.knowledge_base_id,
                "conversationId": conversation_id,
                "userMessageId": user_message.id,
                "assistantMessageId": assistant_message.id,
                "topK": body.top_k,
            },
        )
        idempotency = IdempotencyRecord(
            id=new_id(),
            operation_type="answer",
            owner_id=conversation_id,
            key=idempotency_key,
            fingerprint=operation_fingerprint,
            resource_id=run_id,
            status="pending",
            private_data={
                "userMessageId": user_message.id,
                "assistantMessageId": assistant_message.id,
            },
        )
        session.add_all([user_message, assistant_message, run, idempotency])
        try:
            session.commit()
        except IntegrityError:
            session.rollback()
            dispatcher.release_reservation()
            raise_code("conversation_busy")
        dispatcher.enqueue_reserved(run_id)
        return {
            "userMessage": message_dict(user_message),
            "assistantMessage": message_dict(assistant_message),
            "run": run_dict(run),
        }

"""Conversations API — CRUD for chat sessions."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from sqlalchemy import select, func
from sqlalchemy.orm import joinedload

from amunty.deps import DB, CurrentUser
from amunty.models.conversation import Conversation
from amunty.models.message import Message

router = APIRouter()


class ConversationCreate(BaseModel):
    title: str = "New Chat"
    model_id: str
    system_prompt: str | None = None


class ConversationUpdate(BaseModel):
    title: str | None = None
    model_id: str | None = None
    system_prompt: str | None = None
    is_archived: bool | None = None


class ConversationOut(BaseModel):
    id: str
    title: str
    model_id: str
    system_prompt: str | None
    is_archived: bool
    created_at: str
    updated_at: str
    message_count: int = 0

    model_config = {"from_attributes": True}


class MessageOut(BaseModel):
    id: str
    role: str
    content: str
    tool_calls: str | None
    tool_call_id: str | None
    model_id: str | None
    token_count: int | None
    created_at: str

    model_config = {"from_attributes": True}


class ConversationDetail(BaseModel):
    conversation: ConversationOut
    messages: list[MessageOut]


@router.get("", response_model=list[ConversationOut])
async def list_conversations(db: DB, user: CurrentUser) -> list[ConversationOut]:
    """List all conversations for the current user, newest first."""
    stmt = (
        select(
            Conversation,
            func.count(Message.id).label("message_count"),
        )
        .outerjoin(Message, Message.conversation_id == Conversation.id)
        .where(Conversation.user_id == user.id, Conversation.is_archived == False)  # noqa: E712
        .group_by(Conversation.id)
        .order_by(Conversation.updated_at.desc())
    )
    result = await db.execute(stmt)
    rows = result.all()

    return [
        ConversationOut(
            id=conv.id,
            title=conv.title,
            model_id=conv.model_id,
            system_prompt=conv.system_prompt,
            is_archived=conv.is_archived,
            created_at=conv.created_at.isoformat(),
            updated_at=conv.updated_at.isoformat(),
            message_count=count,
        )
        for conv, count in rows
    ]


@router.post("", response_model=ConversationOut, status_code=201)
async def create_conversation(
    body: ConversationCreate, db: DB, user: CurrentUser
) -> ConversationOut:
    """Create a new conversation."""
    now = datetime.now(UTC)
    conv = Conversation(
        id=str(uuid.uuid4()),
        user_id=user.id,
        title=body.title,
        model_id=body.model_id,
        system_prompt=body.system_prompt,
        created_at=now,
        updated_at=now,
    )
    db.add(conv)
    await db.flush()

    return ConversationOut(
        id=conv.id,
        title=conv.title,
        model_id=conv.model_id,
        system_prompt=conv.system_prompt,
        is_archived=conv.is_archived,
        created_at=conv.created_at.isoformat(),
        updated_at=conv.updated_at.isoformat(),
        message_count=0,
    )


@router.get("/{conversation_id}", response_model=ConversationDetail)
async def get_conversation(conversation_id: str, db: DB, user: CurrentUser) -> ConversationDetail:
    """Get a conversation with all its messages."""
    result = await db.execute(
        select(Conversation)
        .options(joinedload(Conversation.messages))
        .where(
            Conversation.id == conversation_id, Conversation.user_id == user.id
        )
    )
    conv = result.unique().scalar_one_or_none()
    if conv is None:
        raise HTTPException(status_code=404, detail="Conversation not found.")

    # Sort messages by created_at since joinedload doesn't guarantee order
    messages = sorted(conv.messages, key=lambda m: m.created_at)
    msg_count = len(messages)

    return ConversationDetail(
        conversation=ConversationOut(
            id=conv.id,
            title=conv.title,
            model_id=conv.model_id,
            system_prompt=conv.system_prompt,
            is_archived=conv.is_archived,
            created_at=conv.created_at.isoformat(),
            updated_at=conv.updated_at.isoformat(),
            message_count=msg_count,
        ),
        messages=[
            MessageOut(
                id=m.id,
                role=m.role,
                content=m.content,
                tool_calls=m.tool_calls,
                tool_call_id=m.tool_call_id,
                model_id=m.model_id,
                token_count=m.token_count,
                created_at=m.created_at.isoformat(),
            )
            for m in messages
        ],
    )


@router.put("/{conversation_id}", response_model=ConversationOut)
async def update_conversation(
    conversation_id: str, body: ConversationUpdate, db: DB, user: CurrentUser
) -> ConversationOut:
    """Update a conversation's title, model, system prompt, or archive status."""
    result = await db.execute(
        select(Conversation).where(
            Conversation.id == conversation_id, Conversation.user_id == user.id
        )
    )
    conv = result.scalar_one_or_none()
    if conv is None:
        raise HTTPException(status_code=404, detail="Conversation not found.")

    if body.title is not None:
        conv.title = body.title
    if body.model_id is not None:
        conv.model_id = body.model_id
    if body.system_prompt is not None:
        conv.system_prompt = body.system_prompt
    if body.is_archived is not None:
        conv.is_archived = body.is_archived

    conv.updated_at = datetime.now(UTC)
    await db.flush()

    return ConversationOut(
        id=conv.id,
        title=conv.title,
        model_id=conv.model_id,
        system_prompt=conv.system_prompt,
        is_archived=conv.is_archived,
        created_at=conv.created_at.isoformat(),
        updated_at=conv.updated_at.isoformat(),
    )


@router.delete("/{conversation_id}", status_code=204)
async def delete_conversation(conversation_id: str, db: DB, user: CurrentUser) -> None:
    """Archive (soft-delete) a conversation."""
    result = await db.execute(
        select(Conversation).where(
            Conversation.id == conversation_id, Conversation.user_id == user.id
        )
    )
    conv = result.scalar_one_or_none()
    if conv is None:
        raise HTTPException(status_code=404, detail="Conversation not found.")

    conv.is_archived = True
    conv.updated_at = datetime.now(UTC)
    await db.flush()

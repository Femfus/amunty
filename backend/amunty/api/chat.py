"""Chat API — SSE streaming endpoint."""

from __future__ import annotations

import json

from fastapi import APIRouter, Request
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

from amunty.deps import DB, CurrentUser
from amunty.services import chat_engine

router = APIRouter()


class SendMessageRequest(BaseModel):
    session_id: str  # conversation_id
    message: str
    model_id: str | None = None


@router.post("/send")
async def send_message(
    body: SendMessageRequest,
    db: DB,
    user: CurrentUser,
) -> StreamingResponse:
    """Stream an AI response as Server-Sent Events.

    Event format:
        data: {"type": "token", "content": "Hello"}
        data: {"type": "tool_call", "name": "web_search", "params": {...}}
        data: {"type": "done", "message_id": "..."}
        data: {"type": "error", "content": "..."}
    """

    async def event_stream():
        async for event in chat_engine.send_message(
            db=db,
            conversation_id=body.session_id,
            user_id=user.id,
            content=body.message,
            model_id=body.model_id,
        ):
            yield f"data: {json.dumps(event)}\n\n"

    return StreamingResponse(
        event_stream(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",  # Disable nginx buffering
        },
    )

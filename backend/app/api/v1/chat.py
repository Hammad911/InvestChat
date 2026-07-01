"""
Chat API routes with SSE streaming.
"""
from __future__ import annotations

import json
from datetime import datetime
from uuid import UUID

from pydantic import BaseModel
from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import StreamingResponse
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.config import settings
from app.core.limiter import limiter
from app.core.security import get_current_user
from app.db.models import ChatMessage, Document, MessageRole, Project, User
from app.db.session import get_db

router = APIRouter(prefix="/projects/{project_id}/chat", tags=["chat"])


# ── Schemas ──────────────────────────────────────────────────────────────────


class ChatRequest(BaseModel):
    message: str


class ChatMessageResponse(BaseModel):
    id: str
    role: str
    content: str
    citations: list | None
    created_at: datetime

    class Config:
        from_attributes = True


class ChatHistoryResponse(BaseModel):
    messages: list[ChatMessageResponse]
    total: int


# ── Routes ───────────────────────────────────────────────────────────────────


@router.post("")
@limiter.limit(f"{settings.RATE_LIMIT_PER_MINUTE}/minute")
async def chat(
    request: Request,
    project_id: UUID,
    body: ChatRequest,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """Chat with project documents — SSE streamed response."""
    # Verify project access
    result = await db.execute(
        select(Project)
        .where(Project.id == project_id, Project.user_id == user.id)
        .options(selectinload(Project.documents))
    )
    project = result.scalar_one_or_none()
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")

    doc_name_map = {str(d.id): d.original_filename for d in project.documents}

    # Get conversation history
    history_result = await db.execute(
        select(ChatMessage)
        .where(ChatMessage.project_id == project_id)
        .order_by(ChatMessage.created_at.desc())
        .limit(10)
    )
    history_msgs = history_result.scalars().all()
    history = [
        {"role": m.role.value, "content": m.content}
        for m in reversed(list(history_msgs))
    ]

    # Save user message
    user_msg = ChatMessage(
        project_id=project_id,
        role=MessageRole.USER,
        content=body.message,
    )
    db.add(user_msg)
    await db.flush()

    from app.analysis.chat import chat_stream

    full_response = []
    all_citations = []
    request_id = getattr(request.state, "request_id", None)

    async def generate():
        nonlocal full_response, all_citations
        async for chunk in chat_stream(
            question=body.message,
            project_id=str(project_id),
            history=history,
            doc_name_map=doc_name_map,
            request_id=request_id,
        ):
            # Capture tokens for DB storage
            if chunk.startswith("data: "):
                try:
                    data = json.loads(chunk[6:].strip())
                    if data.get("type") == "token":
                        full_response.append(data.get("content", ""))
                    elif data.get("type") == "citations":
                        all_citations = data.get("citations", [])
                except (json.JSONDecodeError, ValueError):
                    pass
            yield chunk

        # Save assistant response to DB
        assistant_msg = ChatMessage(
            project_id=project_id,
            role=MessageRole.ASSISTANT,
            content="".join(full_response),
            citations_json=all_citations,
        )
        db.add(assistant_msg)
        await db.commit()

    return StreamingResponse(
        generate(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


@router.get("/history", response_model=ChatHistoryResponse)
async def get_chat_history(
    project_id: UUID,
    limit: int = 50,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """Get chat history for a project."""
    result = await db.execute(
        select(Project).where(Project.id == project_id, Project.user_id == user.id)
    )
    if not result.scalar_one_or_none():
        raise HTTPException(status_code=404, detail="Project not found")

    msg_result = await db.execute(
        select(ChatMessage)
        .where(ChatMessage.project_id == project_id)
        .order_by(ChatMessage.created_at.asc())
        .limit(limit)
    )
    messages = msg_result.scalars().all()

    return ChatHistoryResponse(
        messages=[
            ChatMessageResponse(
                id=str(m.id),
                role=m.role.value,
                content=m.content,
                citations=m.citations_json,
                created_at=m.created_at,
            )
            for m in messages
        ],
        total=len(messages),
    )

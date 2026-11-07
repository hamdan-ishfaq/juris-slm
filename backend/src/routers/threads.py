"""Chat history and human feedback API."""
from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from db import AnswerFeedback, ChatMessage, ChatThread, Matter, User, get_db
from deps import get_current_user
from services.org_isolation import assert_matter_org

router = APIRouter(prefix="/api/v1", tags=["chat-history"])


class ThreadCreate(BaseModel):
    matter_id: uuid.UUID | None = None
    title: str = Field(default="Chat", max_length=255)


class ThreadResponse(BaseModel):
    id: uuid.UUID
    matter_id: uuid.UUID | None
    title: str


class MessageResponse(BaseModel):
    id: uuid.UUID
    role: str
    content: str
    sources: list | dict | None = None
    model: str | None = None


class FeedbackRequest(BaseModel):
    rating: str = Field(pattern="^(up|down)$")
    correction: str | None = Field(default=None, max_length=8000)
    thread_id: uuid.UUID | None = None
    question: str | None = None
    answer: str | None = None


@router.get("/threads", response_model=list[ThreadResponse])
async def list_threads(
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    query = select(ChatThread).where(ChatThread.user_id == user.id)
    if user.org_id:
        query = query.where(
            (ChatThread.org_id == user.org_id) | (ChatThread.org_id.is_(None))
        )
    rows = await db.execute(query.order_by(ChatThread.created_at.desc()))
    return [
        ThreadResponse(id=t.id, matter_id=t.matter_id, title=t.title)
        for t in rows.scalars().all()
    ]


@router.post("/threads", response_model=ThreadResponse)
async def create_thread(
    body: ThreadCreate,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    org_id = user.org_id
    if body.matter_id:
        matter = await db.get(Matter, body.matter_id)
        if not matter:
            raise HTTPException(status_code=404, detail="Matter not found")
        assert_matter_org(user, matter)
        org_id = matter.org_id or user.org_id
    thread = ChatThread(
        id=uuid.uuid4(),
        user_id=user.id,
        org_id=org_id,
        matter_id=body.matter_id,
        title=body.title,
    )
    db.add(thread)
    await db.commit()
    await db.refresh(thread)
    return ThreadResponse(id=thread.id, matter_id=thread.matter_id, title=thread.title)


@router.get("/threads/{thread_id}/messages", response_model=list[MessageResponse])
async def list_messages(
    thread_id: uuid.UUID,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    thread = await db.get(ChatThread, thread_id)
    if not thread or thread.user_id != user.id:
        raise HTTPException(status_code=404, detail="Thread not found")
    if user.org_id and thread.org_id and user.org_id != thread.org_id:
        raise HTTPException(status_code=404, detail="Thread not found")
    rows = await db.execute(
        select(ChatMessage).where(ChatMessage.thread_id == thread_id).order_by(ChatMessage.created_at)
    )
    return [
        MessageResponse(
            id=m.id,
            role=m.role,
            content=m.content,
            sources=m.sources,
            model=m.model,
        )
        for m in rows.scalars().all()
    ]


async def append_message(
    db: AsyncSession,
    *,
    thread_id: uuid.UUID,
    role: str,
    content: str,
    sources: list | None = None,
    model: str | None = None,
    org_id: uuid.UUID | None = None,
) -> None:
    db.add(
        ChatMessage(
            id=uuid.uuid4(),
            thread_id=thread_id,
            org_id=org_id,
            role=role,
            content=content,
            sources={"items": sources} if sources else None,
            model=model,
        )
    )


@router.post("/feedback")
async def submit_feedback(
    body: FeedbackRequest,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    fb = AnswerFeedback(
        id=uuid.uuid4(),
        user_id=user.id,
        thread_id=body.thread_id,
        rating=body.rating,
        correction=body.correction,
        question=body.question,
        answer=body.answer,
    )
    db.add(fb)
    await db.commit()
    return {"status": "ok", "id": str(fb.id)}

from __future__ import annotations

import json
import logging
import uuid

from fastapi import APIRouter, Depends, HTTPException, Request, status
from fastapi.responses import StreamingResponse
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from config import settings
from db import ChatMessage, ChatThread, User, get_db
from deps import get_current_user
from rate_limit import limiter, rate_limit_exempt
from routers.threads import append_message
from schemas import ChatJobResponse, ChatJobStatusResponse, ChatRequest, ChatResponse
from services.audit_log import log_audit, question_hash
from services.rag import answer_question, answer_question_stream, load_thread_history

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/chat", tags=["chat"])


async def _resolve_thread(db: AsyncSession, user: User, body: ChatRequest) -> uuid.UUID:
    if body.thread_id:
        thread = await db.get(ChatThread, body.thread_id)
        if not thread or thread.user_id != user.id:
            raise HTTPException(status_code=404, detail="Thread not found")
        if user.org_id and thread.org_id and user.org_id != thread.org_id:
            raise HTTPException(status_code=404, detail="Thread not found")
        return thread.id
    thread = ChatThread(
        id=uuid.uuid4(),
        user_id=user.id,
        org_id=user.org_id,
        title=body.message[:80],
    )
    db.add(thread)
    await db.flush()
    return thread.id


async def _audit_chat(
    db: AsyncSession,
    user: User,
    *,
    question: str,
    result: dict,
    thread_id: uuid.UUID,
    use_law_corpus: bool,
) -> None:
    details = {
        "question_hash": question_hash(question),
        "model": result.get("model"),
        "source_count": len(result.get("sources") or []),
        "thread_id": str(thread_id),
        "use_law_corpus": use_law_corpus,
        "cached": result.get("cached", False),
    }
    if settings.audit_log_answers:
        details["answer_preview"] = (result.get("answer") or "")[:500]
    await log_audit(db, user, "chat", "query", resource_id=str(thread_id), details=details)


@router.post("", response_model=ChatResponse)
@limiter.limit("10/minute", exempt_when=rate_limit_exempt)
async def chat(
    request: Request,
    body: ChatRequest,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    try:
        thread_id = await _resolve_thread(db, user, body)
        await append_message(db, thread_id=thread_id, role="user", content=body.message, org_id=user.org_id)
        history = await load_thread_history(db, thread_id, max_turns=settings.chat_history_turns)

        result = await answer_question(
            db,
            body.message,
            use_law_corpus=body.use_law_corpus,
            user=user,
            use_hyde=body.use_hyde,
            history=history,
        )
        await append_message(
            db,
            thread_id=thread_id,
            role="assistant",
            content=result["answer"],
            sources=result.get("sources"),
            model=result.get("model"),
            org_id=user.org_id,
        )
        await _audit_chat(
            db, user, question=body.message, result=result, thread_id=thread_id, use_law_corpus=body.use_law_corpus
        )
        await db.commit()
        return ChatResponse(
            answer=result["answer"],
            model=result["model"],
            sources=result.get("sources") or [],
            thread_id=thread_id,
            cached=result.get("cached", False),
        )
    except HTTPException:
        raise
    except Exception as exc:
        logger.exception("Chat failed")
        raise HTTPException(
            status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Chat service temporarily unavailable.",
        ) from exc


@router.post("/async", response_model=ChatJobResponse)
@limiter.limit("10/minute", exempt_when=rate_limit_exempt)
async def chat_async(
    request: Request,
    body: ChatRequest,
    user: User = Depends(get_current_user),
):
    from services.workflow_jobs import create_job
    from worker import chat_task

    job_id = create_job(
        "chat",
        meta={
            "user_id": str(user.id),
            "message": body.message,
            "use_law_corpus": body.use_law_corpus,
            "use_hyde": body.use_hyde,
            "thread_id": str(body.thread_id) if body.thread_id else None,
        },
    )
    chat_task.delay(job_id)
    return ChatJobResponse(job_id=job_id, status="queued")


@router.get("/jobs/{job_id}", response_model=ChatJobStatusResponse)
async def chat_job_status(
    job_id: str,
    user: User = Depends(get_current_user),
):
    from services.workflow_jobs import get_job

    job = get_job(job_id)
    if not job or job.get("type") != "chat":
        raise HTTPException(status_code=404, detail="Job not found")
    meta = job.get("meta") or {}
    if meta.get("user_id") != str(user.id):
        raise HTTPException(status_code=404, detail="Job not found")
    report = job.get("report") or {}
    return ChatJobStatusResponse(
        job_id=job_id,
        status=job.get("status", "unknown"),
        progress_step=job.get("progress_step"),
        answer=report.get("answer"),
        model=report.get("model"),
        sources=report.get("sources"),
        thread_id=report.get("thread_id"),
        error=job.get("error"),
    )


@router.post("/stream")
@limiter.limit("10/minute", exempt_when=rate_limit_exempt)
async def chat_stream(
    request: Request,
    body: ChatRequest,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    async def event_gen():
        thread_id = None
        try:
            thread_id = await _resolve_thread(db, user, body)
            await append_message(db, thread_id=thread_id, role="user", content=body.message, org_id=user.org_id)
            history = await load_thread_history(db, thread_id, max_turns=settings.chat_history_turns)
            await db.commit()

            full_answer = ""
            sources = []
            model = ""
            async for event in answer_question_stream(
                db,
                body.message,
                use_law_corpus=body.use_law_corpus,
                user=user,
                use_hyde=body.use_hyde,
                history=history,
            ):
                if event.get("type") == "token":
                    full_answer += event.get("content", "")
                if event.get("type") == "sources":
                    sources = event.get("sources") or []
                if event.get("type") == "meta":
                    model = event.get("model") or model
                yield f"data: {json.dumps(event)}\n\n"

            result = {"answer": full_answer, "model": model, "sources": sources, "cached": False}
            await append_message(
                db,
                thread_id=thread_id,
                role="assistant",
                content=full_answer,
                sources=sources,
                model=model,
                org_id=user.org_id,
            )
            await _audit_chat(
                db, user, question=body.message, result=result, thread_id=thread_id, use_law_corpus=body.use_law_corpus
            )
            await db.commit()
            yield f"data: {json.dumps({'type': 'done', 'thread_id': str(thread_id), 'model': model})}\n\n"
        except Exception as exc:
            logger.exception("Chat stream failed")
            yield f"data: {json.dumps({'type': 'error', 'message': str(exc)[:200]})}\n\n"

    return StreamingResponse(event_gen(), media_type="text/event-stream")

"""Audit export endpoints."""
from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import Response
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from db import ChatMessage, ChatThread, Matter, User, get_db
from deps import get_current_user, user_can_access_matter
from services.legal_hold import assert_matter_export_allowed
from services.export_reports import (
    build_analyze_pdf,
    build_analyze_report_markdown,
    build_audit_export,
    build_compare_report_markdown,
    build_markdown_export,
    build_pdf_export,
)

router = APIRouter(prefix="/api/v1/export", tags=["export"])


class ExportRequest(BaseModel):
    matter_id: uuid.UUID | None = None
    thread_id: uuid.UUID | None = None
    format: str = "json"
    question: str | None = None
    answer: str | None = None
    sources: list[dict] | None = None
    document_id: uuid.UUID | None = None
    structured: dict | None = None
    risk: dict | None = None
    filename: str | None = None
    matter_name: str | None = None
    document_name: str | None = None
    prepared_for: str | None = None
    matter_reference: str | None = None
    author_name: str | None = None
    firm_name: str | None = None
    report_title: str | None = None


@router.post("/analyze-report")
async def export_analyze_report(
    body: ExportRequest,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    if not body.matter_id:
        raise HTTPException(status_code=400, detail="matter_id required")
    if not await user_can_access_matter(db, user, body.matter_id):
        raise HTTPException(status_code=404, detail="Matter not found")
    await assert_matter_export_allowed(db, body.matter_id)
    name = body.filename or str(body.document_id or "document")
    md = build_analyze_report_markdown(
        filename=name,
        structured=body.structured,
        risk=body.risk,
        answer=body.answer or "",
    )
    if body.format == "markdown":
        return Response(content=md, media_type="text/markdown")
    if body.format == "pdf":
        try:
            data = build_analyze_pdf(
                user_email=user.email,
                matter_name=name,
                filename=name,
                question=body.question or "Analyze",
                answer=body.answer or "",
                structured=body.structured,
                risk=body.risk,
            )
        except Exception as exc:
            raise HTTPException(status_code=500, detail=f"PDF export failed: {exc}") from exc
        return Response(content=data, media_type="application/pdf")
    payload = {"question": body.question, "answer": body.answer, "structured": body.structured, "risk": body.risk}
    return Response(content=build_audit_export(user_email=user.email, matter_name=name, items=[payload]), media_type="application/json")


@router.post("/compare-report")
async def export_compare_report(
    body: ExportRequest,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    if not body.matter_id or not body.document_id:
        raise HTTPException(status_code=400, detail="matter_id and document_id required")
    if not await user_can_access_matter(db, user, body.matter_id):
        raise HTTPException(status_code=404, detail="Matter not found")
    await assert_matter_export_allowed(db, body.matter_id)
    from services.rag import answer_compare

    result = await answer_compare(
        db,
        body.question or "Compare document against GDPR/BGB baseline",
        document_id=str(body.document_id),
        user=user,
    )
    name = body.filename or str(body.document_id)
    md = build_compare_report_markdown(
        filename=name,
        comparison=result.get("comparison_result") or result.get("answer", ""),
        sources=result.get("sources"),
    )
    if body.format == "markdown":
        return Response(content=md, media_type="text/markdown")
    if body.format == "pdf":
        data = build_pdf_export(
            user_email=user.email,
            matter_name=name,
            items=[{"question": body.question or "Compare", "answer": result.get("answer", ""), "sources": result.get("sources") or []}],
        )
        return Response(content=data, media_type="application/pdf")
    return Response(content=build_audit_export(user_email=user.email, matter_name=name, items=[result]), media_type="application/json")


@router.post("/audit")
async def export_audit(
    body: ExportRequest,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    items: list[dict] = []
    matter_name = "General"

    if body.thread_id:
        thread = await db.get(ChatThread, body.thread_id)
        if not thread or thread.user_id != user.id:
            raise HTTPException(status_code=404, detail="Thread not found")
        rows = await db.execute(
            select(ChatMessage).where(ChatMessage.thread_id == body.thread_id).order_by(ChatMessage.created_at)
        )
        msgs = list(rows.scalars().all())
        for i in range(0, len(msgs) - 1, 2):
            q = msgs[i]
            a = msgs[i + 1] if i + 1 < len(msgs) else None
            if q.role == "user" and a and a.role == "assistant":
                src = a.sources.get("items") if isinstance(a.sources, dict) else a.sources
                items.append({"question": q.content, "answer": a.content, "sources": src or []})

    if body.matter_id:
        if not await user_can_access_matter(db, user, body.matter_id):
            raise HTTPException(status_code=404, detail="Matter not found")
        await assert_matter_export_allowed(db, body.matter_id)
        matter = await db.get(Matter, body.matter_id)
        matter_name = matter.name if matter else str(body.matter_id)
        thread_rows = await db.execute(
            select(ChatThread).where(ChatThread.matter_id == body.matter_id, ChatThread.user_id == user.id)
        )
        for thread in thread_rows.scalars().all():
            msg_rows = await db.execute(
                select(ChatMessage).where(ChatMessage.thread_id == thread.id).order_by(ChatMessage.created_at)
            )
            msgs = list(msg_rows.scalars().all())
            for i in range(0, len(msgs) - 1, 2):
                q = msgs[i]
                a = msgs[i + 1] if i + 1 < len(msgs) else None
                if q.role == "user" and a and a.role == "assistant":
                    src = a.sources.get("items") if isinstance(a.sources, dict) else a.sources
                    items.append({"question": q.content, "answer": a.content, "sources": src or []})

    if body.question and body.answer:
        items.append({"question": body.question, "answer": body.answer, "sources": body.sources or []})

    if body.format == "markdown":
        text = build_markdown_export(user_email=user.email, matter_name=matter_name, items=items)
        return Response(content=text, media_type="text/markdown")

    if body.format == "pdf":
        try:
            matter_label = body.matter_name
            if not matter_label and body.matter_id:
                matter = await db.get(Matter, body.matter_id)
                matter_label = matter.name if matter else str(body.matter_id)
            data = build_pdf_export(
                user_email=user.email,
                matter_name=matter_label or matter_name,
                items=items,
                document_name=body.document_name or body.filename,
                prepared_for=body.prepared_for,
                matter_reference=body.matter_reference,
                author_name=body.author_name,
                firm_name=body.firm_name,
                report_title=body.report_title or "Legal Research Memorandum",
            )
        except Exception as exc:
            raise HTTPException(status_code=500, detail=f"PDF export failed: {exc}") from exc
        return Response(
            content=data,
            media_type="application/pdf",
            headers={"Content-Disposition": "attachment; filename=jurisguard-audit.pdf"},
        )

    data = build_audit_export(user_email=user.email, matter_name=matter_name, items=items)
    return Response(content=data, media_type="application/json")

"""Admin corpus upload API — Phase 10B."""
from __future__ import annotations

import re
import uuid
from datetime import datetime
from pathlib import Path
from uuid import UUID

import aiofiles
from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from config import settings
from db import CorpusSource, User, get_db
from deps import require_role
from services.upload_security import read_upload_bounded, safe_upload_filename

router = APIRouter(prefix="/api/v1/admin/corpus", tags=["corpus-admin"])

CORPUS_DIR = Path(__file__).resolve().parent.parent / "data" / "corpus_uploads"


class CorpusSourceResponse(BaseModel):
    id: UUID
    slug: str
    title: str
    jurisdiction: str
    status: str
    chunk_count: int
    document_id: UUID
    created_at: datetime


def _slugify(value: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "-", value.lower()).strip("-")
    return slug[:64] or "corpus"


@router.get("/sources", response_model=list[CorpusSourceResponse])
async def list_corpus_sources(
    user: User = Depends(require_role("org_admin", "owner")),
    db: AsyncSession = Depends(get_db),
):
    q = select(CorpusSource)
    if user.org_id:
        q = q.where((CorpusSource.org_id == user.org_id) | (CorpusSource.org_id.is_(None)))
    rows = await db.execute(q.order_by(CorpusSource.created_at.desc()))
    return [
        CorpusSourceResponse(
            id=s.id,
            slug=s.slug,
            title=s.title,
            jurisdiction=s.jurisdiction,
            status=s.status,
            chunk_count=s.chunk_count,
            document_id=s.document_id,
            created_at=s.created_at,
        )
        for s in rows.scalars().all()
    ]


@router.post("/upload", response_model=CorpusSourceResponse)
async def upload_corpus_source(
    file: UploadFile = File(...),
    title: str = Form(...),
    jurisdiction: str = Form(default="general"),
    slug: str | None = Form(default=None),
    user: User = Depends(require_role("org_admin", "owner")),
    db: AsyncSession = Depends(get_db),
):
    safe_name = safe_upload_filename(file.filename or "corpus.txt")
    if not safe_name.lower().endswith((".txt", ".pdf", ".md")):
        raise HTTPException(status_code=400, detail="Corpus file must be txt, pdf, or md")
    content = await read_upload_bounded(file, max_bytes=settings.max_upload_bytes)
    source_slug = _slugify(slug or title)
    doc_id = uuid.uuid4()
    CORPUS_DIR.mkdir(parents=True, exist_ok=True)
    dest = CORPUS_DIR / f"{doc_id}_{safe_name}"
    async with aiofiles.open(dest, "wb") as f:
        await f.write(content)

    row = CorpusSource(
        id=uuid.uuid4(),
        org_id=user.org_id,
        slug=source_slug,
        title=title.strip(),
        jurisdiction=jurisdiction.strip(),
        file_path=str(dest),
        document_id=doc_id,
        status="pending",
        created_by=user.id,
    )
    db.add(row)
    await db.commit()
    await db.refresh(row)

    try:
        from worker import ingest_corpus_task

        ingest_corpus_task.delay(str(row.id))
    except Exception:
        pass

    return CorpusSourceResponse(
        id=row.id,
        slug=row.slug,
        title=row.title,
        jurisdiction=row.jurisdiction,
        status=row.status,
        chunk_count=row.chunk_count,
        document_id=row.document_id,
        created_at=row.created_at,
    )


@router.post("/sources/{source_id}/ingest", response_model=CorpusSourceResponse)
async def reingest_corpus_source(
    source_id: UUID,
    user: User = Depends(require_role("org_admin", "owner")),
    db: AsyncSession = Depends(get_db),
):
    row = await db.get(CorpusSource, source_id)
    if not row:
        raise HTTPException(status_code=404, detail="Source not found")
    if user.org_id and row.org_id and row.org_id != user.org_id:
        raise HTTPException(status_code=404, detail="Source not found")
    row.status = "pending"
    row.chunk_count = 0
    await db.commit()
    await db.refresh(row)
    try:
        from worker import ingest_corpus_task

        ingest_corpus_task.delay(str(row.id))
    except Exception:
        pass
    return CorpusSourceResponse(
        id=row.id,
        slug=row.slug,
        title=row.title,
        jurisdiction=row.jurisdiction,
        status=row.status,
        chunk_count=row.chunk_count,
        document_id=row.document_id,
        created_at=row.created_at,
    )

"""Phase 9B — legal hold checks and enforcement."""
from __future__ import annotations

import uuid

from fastapi import HTTPException, status
from sqlalchemy import or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from config import settings
from db import LegalHold, MatterDocument


async def active_matter_hold_exists(db: AsyncSession, matter_id: uuid.UUID) -> bool:
    result = await db.execute(
        select(LegalHold.id).where(
            LegalHold.matter_id == matter_id,
            LegalHold.document_id.is_(None),
            LegalHold.status == "active",
        ).limit(1)
    )
    return result.scalar_one_or_none() is not None


async def active_document_hold_exists(
    db: AsyncSession,
    *,
    document_id: uuid.UUID,
    matter_id: uuid.UUID | None = None,
) -> bool:
    clauses = [
        LegalHold.document_id == document_id,
        LegalHold.status == "active",
    ]
    result = await db.execute(select(LegalHold.id).where(*clauses).limit(1))
    if result.scalar_one_or_none() is not None:
        return True
    if matter_id and await active_matter_hold_exists(db, matter_id):
        return True
    return False


async def assert_matter_deletable(db: AsyncSession, matter_id: uuid.UUID) -> None:
    if await active_matter_hold_exists(db, matter_id):
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Matter is under active legal hold and cannot be deleted",
        )


async def assert_document_deletable(db: AsyncSession, document_id: uuid.UUID, matter_id: uuid.UUID) -> None:
    if await active_document_hold_exists(db, document_id=document_id, matter_id=matter_id):
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Document is under active legal hold and cannot be deleted",
        )


async def assert_document_editable(db: AsyncSession, document_id: uuid.UUID, matter_id: uuid.UUID) -> None:
    if await active_document_hold_exists(db, document_id=document_id, matter_id=matter_id):
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Document is under active legal hold and is read-only",
        )


async def assert_matter_export_allowed(db: AsyncSession, matter_id: uuid.UUID) -> None:
    if settings.legal_hold_allow_export:
        return
    if await active_matter_hold_exists(db, matter_id):
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Export blocked while matter is under legal hold",
        )


async def chunks_under_hold(db: AsyncSession, document_id: uuid.UUID) -> bool:
    doc = await db.get(MatterDocument, document_id)
    if not doc:
        return False
    return await active_document_hold_exists(db, document_id=document_id, matter_id=doc.matter_id)


async def list_holds_for_matter(db: AsyncSession, matter_id: uuid.UUID) -> list[LegalHold]:
    result = await db.execute(
        select(LegalHold)
        .where(
            or_(
                LegalHold.matter_id == matter_id,
                LegalHold.document_id.in_(
                    select(MatterDocument.id).where(MatterDocument.matter_id == matter_id)
                ),
            )
        )
        .order_by(LegalHold.placed_at.desc())
    )
    return list(result.scalars().all())

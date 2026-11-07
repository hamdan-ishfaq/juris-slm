"""Clause library API — Phase 10E."""
from __future__ import annotations

import uuid
from datetime import datetime, timezone
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from db import ClauseLibraryItem, User, get_db
from deps import get_current_user, require_role

router = APIRouter(prefix="/api/v1/clause-library", tags=["clause-library"])


class ClauseLibraryCreate(BaseModel):
    clause_type: str = Field(min_length=1, max_length=64)
    title: str = Field(min_length=1, max_length=255)
    body_text: str = Field(min_length=1)
    jurisdiction: str = Field(default="general", max_length=64)
    is_standard: bool = True


class ClauseLibraryUpdate(BaseModel):
    title: str | None = Field(default=None, max_length=255)
    body_text: str | None = None
    jurisdiction: str | None = Field(default=None, max_length=64)
    is_standard: bool | None = None


class ClauseLibraryResponse(BaseModel):
    id: UUID
    org_id: UUID
    clause_type: str
    title: str
    body_text: str
    jurisdiction: str
    is_standard: bool
    created_at: datetime
    updated_at: datetime


def _to_response(item: ClauseLibraryItem) -> ClauseLibraryResponse:
    return ClauseLibraryResponse(
        id=item.id,
        org_id=item.org_id,
        clause_type=item.clause_type,
        title=item.title,
        body_text=item.body_text,
        jurisdiction=item.jurisdiction,
        is_standard=item.is_standard,
        created_at=item.created_at,
        updated_at=item.updated_at,
    )


@router.get("", response_model=list[ClauseLibraryResponse])
async def list_clauses(
    clause_type: str | None = None,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    if not user.org_id:
        return []
    q = select(ClauseLibraryItem).where(ClauseLibraryItem.org_id == user.org_id)
    if clause_type:
        q = q.where(ClauseLibraryItem.clause_type == clause_type)
    rows = await db.execute(q.order_by(ClauseLibraryItem.updated_at.desc()))
    return [_to_response(i) for i in rows.scalars().all()]


@router.post("", response_model=ClauseLibraryResponse, status_code=status.HTTP_201_CREATED)
async def create_clause(
    body: ClauseLibraryCreate,
    user: User = Depends(require_role("matter_lead", "org_admin", "owner")),
    db: AsyncSession = Depends(get_db),
):
    if not user.org_id:
        raise HTTPException(status_code=400, detail="User must belong to an organization")
    item = ClauseLibraryItem(
        id=uuid.uuid4(),
        org_id=user.org_id,
        clause_type=body.clause_type.strip(),
        title=body.title.strip(),
        body_text=body.body_text.strip(),
        jurisdiction=body.jurisdiction.strip(),
        is_standard=body.is_standard,
        created_by=user.id,
    )
    db.add(item)
    await db.commit()
    await db.refresh(item)
    return _to_response(item)


@router.patch("/{item_id}", response_model=ClauseLibraryResponse)
async def update_clause(
    item_id: UUID,
    body: ClauseLibraryUpdate,
    user: User = Depends(require_role("matter_lead", "org_admin", "owner")),
    db: AsyncSession = Depends(get_db),
):
    item = await db.get(ClauseLibraryItem, item_id)
    if not item or item.org_id != user.org_id:
        raise HTTPException(status_code=404, detail="Clause not found")
    if body.title is not None:
        item.title = body.title.strip()
    if body.body_text is not None:
        item.body_text = body.body_text.strip()
    if body.jurisdiction is not None:
        item.jurisdiction = body.jurisdiction.strip()
    if body.is_standard is not None:
        item.is_standard = body.is_standard
    item.updated_at = datetime.now(timezone.utc)
    await db.commit()
    await db.refresh(item)
    return _to_response(item)


@router.delete("/{item_id}")
async def delete_clause(
    item_id: UUID,
    user: User = Depends(require_role("org_admin", "owner")),
    db: AsyncSession = Depends(get_db),
):
    item = await db.get(ClauseLibraryItem, item_id)
    if not item or item.org_id != user.org_id:
        raise HTTPException(status_code=404, detail="Clause not found")
    await db.delete(item)
    await db.commit()
    return {"ok": True}

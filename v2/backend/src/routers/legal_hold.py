"""Phase 9B — legal hold API."""
from __future__ import annotations

import uuid
from datetime import datetime, timezone
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from db import LegalHold, Matter, MatterDocument, User, get_db
from deps import get_current_user, require_matter_access
from services.access_control import admin_role_at_least
from services.audit_log import log_audit
from services.legal_hold import list_holds_for_matter
from services.org_isolation import assert_matter_org

router = APIRouter(prefix="/api/v1", tags=["legal-hold"])


class LegalHoldCreate(BaseModel):
    reason: str = Field(min_length=3, max_length=2000)


class LegalHoldResponse(BaseModel):
    id: uuid.UUID
    org_id: uuid.UUID
    matter_id: uuid.UUID | None
    document_id: uuid.UUID | None
    reason: str
    placed_by: uuid.UUID | None
    placed_at: datetime
    released_at: datetime | None
    status: str


def _require_hold_admin(user: User) -> None:
    if not admin_role_at_least(user.role, "org_admin"):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Insufficient role")


def _to_response(hold: LegalHold) -> LegalHoldResponse:
    return LegalHoldResponse(
        id=hold.id,
        org_id=hold.org_id,
        matter_id=hold.matter_id,
        document_id=hold.document_id,
        reason=hold.reason,
        placed_by=hold.placed_by,
        placed_at=hold.placed_at,
        released_at=hold.released_at,
        status=hold.status,
    )


@router.post("/matters/{matter_id}/legal-hold", response_model=LegalHoldResponse)
async def place_matter_hold(
    matter_id: UUID,
    body: LegalHoldCreate,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    _require_hold_admin(user)
    matter = await require_matter_access(matter_id, user, db, min_role="owner")
    if not user.org_id:
        raise HTTPException(status_code=400, detail="User must belong to an organization")
    hold = LegalHold(
        id=uuid.uuid4(),
        org_id=user.org_id,
        matter_id=matter.id,
        reason=body.reason.strip(),
        placed_by=user.id,
        status="active",
    )
    db.add(hold)
    await log_audit(
        db, user, "legal_hold_place", "legal_hold", str(hold.id), {"matter_id": str(matter_id), "reason": body.reason.strip()}
    )
    await db.commit()
    await db.refresh(hold)
    return _to_response(hold)


@router.delete("/matters/{matter_id}/legal-hold/{hold_id}", response_model=LegalHoldResponse)
async def release_matter_hold(
    matter_id: UUID,
    hold_id: UUID,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    _require_hold_admin(user)
    await require_matter_access(matter_id, user, db, min_role="owner")
    hold = await db.get(LegalHold, hold_id)
    if not hold or hold.matter_id != matter_id:
        raise HTTPException(status_code=404, detail="Legal hold not found")
    assert_matter_org(user, await db.get(Matter, matter_id))
    if hold.status == "released":
        return _to_response(hold)
    hold.status = "released"
    hold.released_at = datetime.now(timezone.utc)
    await log_audit(db, user, "legal_hold_release", "legal_hold", str(hold.id), {"matter_id": str(matter_id)})
    await db.commit()
    await db.refresh(hold)
    return _to_response(hold)


@router.get("/matters/{matter_id}/legal-holds", response_model=list[LegalHoldResponse])
async def list_matter_holds(
    matter_id: UUID,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    if not admin_role_at_least(user.role, "matter_lead"):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Insufficient role")
    await require_matter_access(matter_id, user, db, min_role="viewer")
    holds = await list_holds_for_matter(db, matter_id)
    return [_to_response(h) for h in holds]


@router.post("/documents/{document_id}/legal-hold", response_model=LegalHoldResponse)
async def place_document_hold(
    document_id: UUID,
    body: LegalHoldCreate,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    _require_hold_admin(user)
    doc = await db.get(MatterDocument, document_id)
    if not doc:
        raise HTTPException(status_code=404, detail="Document not found")
    matter = await db.get(Matter, doc.matter_id)
    if not matter:
        raise HTTPException(status_code=404, detail="Matter not found")
    assert_matter_org(user, matter)
    await require_matter_access(doc.matter_id, user, db, min_role="owner")
    if not user.org_id:
        raise HTTPException(status_code=400, detail="User must belong to an organization")
    hold = LegalHold(
        id=uuid.uuid4(),
        org_id=user.org_id,
        matter_id=None,
        document_id=document_id,
        reason=body.reason.strip(),
        placed_by=user.id,
        status="active",
    )
    db.add(hold)
    await log_audit(
        db,
        user,
        "legal_hold_place",
        "legal_hold",
        str(hold.id),
        {"document_id": str(document_id), "matter_id": str(doc.matter_id), "reason": body.reason.strip()},
    )
    await db.commit()
    await db.refresh(hold)
    return _to_response(hold)

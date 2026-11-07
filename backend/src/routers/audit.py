import csv
import io
from datetime import datetime
from uuid import UUID

from fastapi import APIRouter, Depends, Query
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from db import AuditEvent, User, get_db
from deps import require_role
from schemas import AuditEventResponse, AuditListResponse
from services.audit_chain import seal_org_chain, verify_chain

router = APIRouter(prefix="/api/v1/audit", tags=["audit"])


class AuditVerifyResponse(BaseModel):
    valid: bool
    events_checked: int
    org_id: str | None = None
    chain_tail: str | None = None
    first_invalid_id: str | None = None
    reason: str | None = None


class AuditSealResponse(BaseModel):
    sealed: bool
    seal_id: str | None = None
    chain_tail_hash: str | None = None
    event_count: int | None = None


def _audit_query(user: User, db: AsyncSession):
    query = select(AuditEvent)
    if user.org_id:
        query = query.where(AuditEvent.org_id == user.org_id)
    return query


@router.get("", response_model=AuditListResponse)
async def list_audit_events(
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=50, ge=1, le=200),
    user_id: UUID | None = None,
    action: str | None = None,
    resource_type: str | None = None,
    since: datetime | None = None,
    until: datetime | None = None,
    user: User = Depends(require_role("org_admin", "owner")),
    db: AsyncSession = Depends(get_db),
):
    query = _audit_query(user, db)
    if user_id:
        query = query.where(AuditEvent.user_id == user_id)
    if action:
        query = query.where(AuditEvent.action == action)
    if resource_type:
        query = query.where(AuditEvent.resource_type == resource_type)
    if since:
        query = query.where(AuditEvent.timestamp >= since)
    if until:
        query = query.where(AuditEvent.timestamp <= until)

    count_q = select(func.count(AuditEvent.id))
    if user.org_id:
        count_q = count_q.where(AuditEvent.org_id == user.org_id)
    if user_id:
        count_q = count_q.where(AuditEvent.user_id == user_id)
    if action:
        count_q = count_q.where(AuditEvent.action == action)
    if resource_type:
        count_q = count_q.where(AuditEvent.resource_type == resource_type)
    if since:
        count_q = count_q.where(AuditEvent.timestamp >= since)
    if until:
        count_q = count_q.where(AuditEvent.timestamp <= until)
    total = int((await db.execute(count_q)).scalar_one())

    rows = await db.execute(
        query.order_by(AuditEvent.timestamp.desc()).offset((page - 1) * page_size).limit(page_size)
    )
    items = [
        AuditEventResponse(
            id=e.id,
            user_id=e.user_id,
            org_id=e.org_id,
            action=e.action,
            resource_type=e.resource_type,
            resource_id=e.resource_id,
            timestamp=e.timestamp,
            details=e.details,
        )
        for e in rows.scalars().all()
    ]
    return AuditListResponse(items=items, total=total, page=page, page_size=page_size)


@router.get("/export")
async def export_audit_csv(
    user: User = Depends(require_role("org_admin", "owner")),
    db: AsyncSession = Depends(get_db),
):
    query = _audit_query(user, db).order_by(AuditEvent.timestamp.desc()).limit(5000)
    rows = await db.execute(query)
    events = rows.scalars().all()

    buffer = io.StringIO()
    writer = csv.writer(buffer)
    writer.writerow(["id", "user_id", "org_id", "action", "resource_type", "resource_id", "timestamp", "details"])
    for e in events:
        writer.writerow(
            [
                str(e.id),
                str(e.user_id),
                str(e.org_id) if e.org_id else "",
                e.action,
                e.resource_type,
                e.resource_id or "",
                e.timestamp.isoformat(),
                e.details,
            ]
        )
    buffer.seek(0)
    return StreamingResponse(
        iter([buffer.getvalue()]),
        media_type="text/csv",
        headers={"Content-Disposition": "attachment; filename=audit_export.csv"},
    )


@router.get("/verify", response_model=AuditVerifyResponse)
async def verify_audit_chain(
    since: datetime | None = None,
    until: datetime | None = None,
    user: User = Depends(require_role("org_admin", "owner")),
    db: AsyncSession = Depends(get_db),
):
    result = await verify_chain(db, org_id=user.org_id, since=since, until=until)
    return AuditVerifyResponse(**result)


@router.post("/seal", response_model=AuditSealResponse)
async def seal_audit_chain(
    user: User = Depends(require_role("org_admin", "owner")),
    db: AsyncSession = Depends(get_db),
):
    seal = await seal_org_chain(db, user.org_id)
    if not seal:
        return AuditSealResponse(sealed=False)
    await db.commit()
    return AuditSealResponse(
        sealed=True,
        seal_id=str(seal.id),
        chain_tail_hash=seal.chain_tail_hash,
        event_count=seal.event_count,
    )

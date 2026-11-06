"""Phase 9E — SHA-256 hash chain for immutable audit events."""
from __future__ import annotations

import hashlib
import json
import uuid
from datetime import date, datetime, timezone
from typing import Any

from sqlalchemy import and_, select
from sqlalchemy.ext.asyncio import AsyncSession

from db import AuditEvent, AuditSeal

GENESIS_HASH = hashlib.sha256(b"GENESIS").hexdigest()


def _canonical_payload(
    *,
    event_id: uuid.UUID,
    user_id: uuid.UUID,
    org_id: uuid.UUID | None,
    action: str,
    resource_type: str,
    resource_id: str | None,
    timestamp: datetime,
    details: dict | None,
) -> dict[str, Any]:
    return {
        "id": str(event_id),
        "user_id": str(user_id),
        "org_id": str(org_id) if org_id else None,
        "action": action,
        "resource_type": resource_type,
        "resource_id": resource_id,
        "timestamp": timestamp.isoformat(),
        "details": details or {},
    }


def compute_row_hash(prev_hash: str, payload: dict[str, Any]) -> str:
    canonical = json.dumps(payload, sort_keys=True, separators=(",", ":"), default=str)
    return hashlib.sha256(f"{prev_hash}|{canonical}".encode()).hexdigest()


async def last_row_hash(db: AsyncSession, org_id: uuid.UUID | None) -> str:
    q = select(AuditEvent.row_hash).order_by(AuditEvent.timestamp.desc(), AuditEvent.id.desc()).limit(1)
    if org_id is None:
        q = q.where(AuditEvent.org_id.is_(None))
    else:
        q = q.where(AuditEvent.org_id == org_id)
    result = await db.execute(q)
    tail = result.scalar_one_or_none()
    return tail or GENESIS_HASH


def hash_for_event(event: AuditEvent, prev_hash: str) -> str:
    payload = _canonical_payload(
        event_id=event.id,
        user_id=event.user_id,
        org_id=event.org_id,
        action=event.action,
        resource_type=event.resource_type,
        resource_id=event.resource_id,
        timestamp=event.timestamp,
        details=event.details,
    )
    return compute_row_hash(prev_hash, payload)


async def verify_chain(
    db: AsyncSession,
    *,
    org_id: uuid.UUID | None,
    since: datetime | None = None,
    until: datetime | None = None,
) -> dict[str, Any]:
    """Verify hash chain integrity for an org (or global null-org chain)."""
    q = select(AuditEvent).order_by(AuditEvent.timestamp.asc(), AuditEvent.id.asc())
    if org_id is None:
        q = q.where(AuditEvent.org_id.is_(None))
    else:
        q = q.where(AuditEvent.org_id == org_id)
    events = (await db.execute(q)).scalars().all()

    if not events:
        return {"valid": True, "events_checked": 0, "org_id": str(org_id) if org_id else None}

    prev = GENESIS_HASH
    checked = 0
    for ev in events:
        in_range = (not since or ev.timestamp >= since) and (not until or ev.timestamp <= until)
        if ev.prev_hash != prev:
            return {
                "valid": False,
                "events_checked": checked,
                "first_invalid_id": str(ev.id),
                "reason": "prev_hash_mismatch",
                "org_id": str(org_id) if org_id else None,
            }
        expected = hash_for_event(ev, prev)
        if ev.row_hash != expected:
            return {
                "valid": False,
                "events_checked": checked,
                "first_invalid_id": str(ev.id),
                "reason": "row_hash_mismatch",
                "org_id": str(org_id) if org_id else None,
            }
        prev = ev.row_hash or prev
        if in_range:
            checked += 1

    return {"valid": True, "events_checked": checked, "chain_tail": prev, "org_id": str(org_id) if org_id else None}


async def seal_org_chain(db: AsyncSession, org_id: uuid.UUID | None, seal_date: date | None = None) -> AuditSeal | None:
    """Write daily seal record with chain tail hash."""
    day = seal_date or datetime.now(timezone.utc).date()
    existing = await db.execute(
        select(AuditSeal).where(
            AuditSeal.org_id == org_id if org_id else AuditSeal.org_id.is_(None),
            AuditSeal.seal_date == day,
        )
    )
    if existing.scalar_one_or_none():
        return None

    q = select(AuditEvent).order_by(AuditEvent.timestamp.asc(), AuditEvent.id.asc())
    if org_id is None:
        q = q.where(AuditEvent.org_id.is_(None))
    else:
        q = q.where(AuditEvent.org_id == org_id)
    events = (await db.execute(q)).scalars().all()
    if not events:
        return None

    verify = await verify_chain(db, org_id=org_id)
    if not verify.get("valid"):
        raise ValueError("Cannot seal invalid audit chain")

    seal = AuditSeal(
        id=uuid.uuid4(),
        org_id=org_id,
        seal_date=day,
        event_count=len(events),
        first_event_id=events[0].id,
        last_event_id=events[-1].id,
        chain_tail_hash=events[-1].row_hash or GENESIS_HASH,
    )
    db.add(seal)
    return seal

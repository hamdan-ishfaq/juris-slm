"""Audit helpers for chat and other routers."""
from __future__ import annotations

import hashlib
import uuid
from datetime import datetime, timezone

from sqlalchemy.ext.asyncio import AsyncSession

from db import AuditEvent, User
from services.audit_chain import hash_for_event, last_row_hash


async def log_audit(
    db: AsyncSession,
    user: User,
    action: str,
    resource_type: str,
    resource_id: str | None = None,
    details: dict | None = None,
) -> None:
    event_id = uuid.uuid4()
    ts = datetime.now(timezone.utc)
    prev = await last_row_hash(db, user.org_id)
    event = AuditEvent(
        id=event_id,
        user_id=user.id,
        org_id=user.org_id,
        action=action,
        resource_type=resource_type,
        resource_id=resource_id,
        timestamp=ts,
        details=details or {},
    )
    event.prev_hash = prev
    event.row_hash = hash_for_event(event, prev)
    db.add(event)


def question_hash(text: str) -> str:
    return hashlib.sha256(text.encode()).hexdigest()[:16]

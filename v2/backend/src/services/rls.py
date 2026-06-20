"""Postgres RLS session context — Phase 9A."""
from __future__ import annotations

import uuid

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from config import settings


async def set_rls_org_context(db: AsyncSession, org_id: uuid.UUID | None) -> None:
    if not settings.rls_enabled:
        return
    if org_id is None:
        await db.execute(text("SELECT set_config('app.org_id', '', true)"))
        return
    await db.execute(
        text("SELECT set_config('app.org_id', :org_id, true)"),
        {"org_id": str(org_id)},
    )


async def bypass_rls(db: AsyncSession) -> None:
    """Migration/admin paths only."""
    if not settings.rls_enabled:
        return
    await db.execute(text("SELECT set_config('app.bypass_rls', 'on', true)"))

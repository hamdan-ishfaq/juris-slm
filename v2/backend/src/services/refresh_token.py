"""Refresh token issuance and rotation — Phase 10D."""
from __future__ import annotations

import hashlib
import secrets
import uuid
from datetime import datetime, timedelta, timezone

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from config import settings
from db import RefreshToken, User


def _hash_token(raw: str) -> str:
    return hashlib.sha256(raw.encode()).hexdigest()


def _new_raw_token() -> str:
    return secrets.token_urlsafe(48)


async def issue_refresh_token(
    db: AsyncSession,
    user: User,
    *,
    user_agent: str | None = None,
) -> str:
    raw = _new_raw_token()
    row = RefreshToken(
        id=uuid.uuid4(),
        user_id=user.id,
        token_hash=_hash_token(raw),
        expires_at=datetime.now(timezone.utc) + timedelta(days=settings.auth_refresh_expire_days),
        user_agent=(user_agent or "")[:512] or None,
    )
    db.add(row)
    await db.flush()
    return raw


async def rotate_refresh_token(
    db: AsyncSession,
    raw_token: str,
    *,
    user_agent: str | None = None,
) -> tuple[User, str] | None:
    token_hash = _hash_token(raw_token)
    result = await db.execute(
        select(RefreshToken).where(
            RefreshToken.token_hash == token_hash,
            RefreshToken.revoked_at.is_(None),
        )
    )
    row = result.scalar_one_or_none()
    if not row or row.expires_at < datetime.now(timezone.utc):
        return None
    user = await db.get(User, row.user_id)
    if not user or user.disabled_at is not None:
        return None
    row.revoked_at = datetime.now(timezone.utc)
    new_raw = await issue_refresh_token(db, user, user_agent=user_agent)
    return user, new_raw


async def revoke_user_sessions(db: AsyncSession, user_id: uuid.UUID) -> int:
    result = await db.execute(
        select(RefreshToken).where(
            RefreshToken.user_id == user_id,
            RefreshToken.revoked_at.is_(None),
        )
    )
    rows = result.scalars().all()
    now = datetime.now(timezone.utc)
    for row in rows:
        row.revoked_at = now
    return len(rows)

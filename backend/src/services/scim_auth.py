"""Phase 9C — SCIM bearer token validation."""
from __future__ import annotations

import hashlib
import secrets
import uuid

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from config import settings
from db import Organization, ScimToken, get_db

_bearer = HTTPBearer(auto_error=False)


def hash_scim_token(raw: str) -> str:
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def generate_scim_token() -> str:
    return secrets.token_urlsafe(32)


async def get_scim_org(
    credentials: HTTPAuthorizationCredentials | None = Depends(_bearer),
    db: AsyncSession = Depends(get_db),
) -> Organization:
    if not settings.scim_enabled:
        raise HTTPException(status_code=404, detail="SCIM not enabled")
    if credentials is None or credentials.scheme.lower() != "bearer":
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="SCIM bearer token required")
    token_hash = hash_scim_token(credentials.credentials)
    result = await db.execute(
        select(ScimToken, Organization)
        .join(Organization, ScimToken.org_id == Organization.id)
        .where(ScimToken.token_hash == token_hash, ScimToken.revoked_at.is_(None))
    )
    row = result.first()
    if not row:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid SCIM token")
    _token, org = row
    return org

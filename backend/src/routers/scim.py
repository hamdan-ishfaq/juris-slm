"""Phase 9C — SCIM 2.0 Users API."""
from __future__ import annotations

import uuid
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from pydantic import BaseModel
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from auth_utils import hash_password
from db import Organization, User, get_db
from services.rls import bypass_rls, set_rls_org_context
from services.scim_auth import get_scim_org
from services.sso_provision import provision_sso_user

router = APIRouter(prefix="/scim/v2", tags=["scim"])


class ScimName(BaseModel):
    formatted: str | None = None


class ScimUserResource(BaseModel):
    schemas: list[str] = ["urn:ietf:params:scim:schemas:core:2.0:User"]
    id: str
    userName: str
    name: ScimName | None = None
    active: bool = True
    externalId: str | None = None


class ScimListResponse(BaseModel):
    schemas: list[str] = ["urn:ietf:params:scim:api:messages:2.0:ListResponse"]
    totalResults: int
    startIndex: int
    itemsPerPage: int
    Resources: list[ScimUserResource]


def _to_scim(user: User) -> ScimUserResource:
    return ScimUserResource(
        id=str(user.id),
        userName=user.email,
        name=ScimName(formatted=user.email),
        active=user.disabled_at is None,
        externalId=user.external_id,
    )


@router.get("/Users", response_model=ScimListResponse)
async def list_users(
    startIndex: int = Query(default=1, ge=1),
    count: int = Query(default=100, ge=1, le=200),
    filter: str | None = None,
    org: Organization = Depends(get_scim_org),
    db: AsyncSession = Depends(get_db),
):
    await bypass_rls(db)
    base = select(User).where(User.org_id == org.id)
    if filter and "userName eq" in filter:
        email = filter.split('"')[1] if '"' in filter else filter.split()[-1]
        base = base.where(User.email == email.lower())
    total = int((await db.execute(select(func.count(User.id)).where(User.org_id == org.id))).scalar_one())
    rows = await db.execute(base.offset(startIndex - 1).limit(count))
    users = list(rows.scalars().all())
    return ScimListResponse(
        totalResults=total,
        startIndex=startIndex,
        itemsPerPage=len(users),
        Resources=[_to_scim(u) for u in users],
    )


@router.get("/Users/{user_id}", response_model=ScimUserResource)
async def get_user(
    user_id: uuid.UUID,
    org: Organization = Depends(get_scim_org),
    db: AsyncSession = Depends(get_db),
):
    await bypass_rls(db)
    user = await db.get(User, user_id)
    if not user or user.org_id != org.id:
        raise HTTPException(status_code=404, detail="User not found")
    return _to_scim(user)


@router.post("/Users", response_model=ScimUserResource, status_code=201)
async def create_user(
    request: Request,
    org: Organization = Depends(get_scim_org),
    db: AsyncSession = Depends(get_db),
):
    await bypass_rls(db)
    body = await request.json()
    email = (body.get("userName") or body.get("emails", [{}])[0].get("value") or "").lower().strip()
    if not email:
        raise HTTPException(status_code=400, detail="userName required")
    external_id = body.get("externalId")
    groups = [g.get("display") for g in body.get("groups", []) if g.get("display")]
    user = await provision_sso_user(
        db,
        email=email,
        external_id=external_id,
        idp_source="scim",
        groups=groups,
        org=org,
    )
    if body.get("password"):
        user.password_hash = hash_password(body["password"])
    await set_rls_org_context(db, org.id)
    await db.commit()
    await db.refresh(user)
    return _to_scim(user)


@router.patch("/Users/{user_id}", response_model=ScimUserResource)
async def patch_user(
    user_id: uuid.UUID,
    request: Request,
    org: Organization = Depends(get_scim_org),
    db: AsyncSession = Depends(get_db),
):
    await bypass_rls(db)
    user = await db.get(User, user_id)
    if not user or user.org_id != org.id:
        raise HTTPException(status_code=404, detail="User not found")
    body = await request.json()
    for op in body.get("Operations", []):
        path = (op.get("path") or "").lower()
        value = op.get("value")
        if path == "active":
            active = value if isinstance(value, bool) else str(value).lower() == "true"
            user.disabled_at = None if active else datetime.now(timezone.utc)
        if path == "username" and value:
            user.email = str(value).lower()
        if path == "externalid" and value:
            user.external_id = str(value)
    await db.commit()
    await db.refresh(user)
    return _to_scim(user)


@router.delete("/Users/{user_id}", status_code=204)
async def delete_user(
    user_id: uuid.UUID,
    org: Organization = Depends(get_scim_org),
    db: AsyncSession = Depends(get_db),
):
    await bypass_rls(db)
    user = await db.get(User, user_id)
    if not user or user.org_id != org.id:
        raise HTTPException(status_code=404, detail="User not found")
    user.disabled_at = datetime.now(timezone.utc)
    await db.commit()

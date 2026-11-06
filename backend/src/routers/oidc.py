"""Phase 9C — OIDC SSO (extended)."""
from __future__ import annotations

import uuid

import httpx
from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import RedirectResponse
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from auth_utils import create_access_token
from config import settings
from db import Organization, get_db
from routers.auth import _user_response
from services.rls import set_rls_org_context
from services.sso_provision import provision_sso_user, resolve_org_for_sso

router = APIRouter(prefix="/api/v1/auth/oidc", tags=["oidc"])


class OidcTokenExchange(BaseModel):
    code: str


@router.get("/login")
async def oidc_login():
    if not settings.oidc_enabled:
        raise HTTPException(status_code=404, detail="OIDC not enabled")
    issuer = settings.oidc_issuer_url.rstrip("/")
    url = (
        f"{issuer}/protocol/openid-connect/auth"
        f"?client_id={settings.oidc_client_id}"
        f"&response_type=code"
        f"&scope=openid%20email%20profile"
        f"&redirect_uri={settings.oidc_redirect_uri}"
    )
    return RedirectResponse(url)


@router.post("/token")
async def oidc_token_exchange(body: OidcTokenExchange, db: AsyncSession = Depends(get_db)):
    """Frontend callback exchanges authorization code for JurisGuard JWT."""
    if not settings.oidc_enabled:
        raise HTTPException(status_code=404, detail="OIDC not enabled")
    profile, _access = await _fetch_oidc_profile(body.code)
    org = await _resolve_org_from_claims(db, profile)
    user = await provision_sso_user(
        db,
        email=profile["email"],
        external_id=profile.get("sub"),
        idp_source="oidc",
        groups=profile.get("groups"),
        org=org,
    )
    await set_rls_org_context(db, user.org_id)
    await db.commit()
    await db.refresh(user)
    extra = {"role": user.role, "org_id": str(user.org_id) if user.org_id else None}
    jwt = create_access_token(str(user.id), extra=extra)
    return {"access_token": jwt, "token_type": "bearer", "user": _user_response(user)}


@router.get("/callback")
async def oidc_callback(code: str = Query(...), db: AsyncSession = Depends(get_db)):
    """Legacy server-side callback — redirects to frontend with token."""
    if not settings.oidc_enabled:
        raise HTTPException(status_code=404, detail="OIDC not enabled")
    profile, _access = await _fetch_oidc_profile(code)
    org = await _resolve_org_from_claims(db, profile)
    user = await provision_sso_user(
        db,
        email=profile["email"],
        external_id=profile.get("sub"),
        idp_source="oidc",
        groups=profile.get("groups"),
        org=org,
    )
    await set_rls_org_context(db, user.org_id)
    await db.commit()
    await db.refresh(user)
    extra = {"role": user.role, "org_id": str(user.org_id) if user.org_id else None}
    jwt = create_access_token(str(user.id), extra=extra)
    frontend = settings.oidc_redirect_uri.rsplit("/auth/callback", 1)[0] or "http://localhost:5173"
    return RedirectResponse(f"{frontend}/auth/callback?token={jwt}")


@router.get("/logout")
async def oidc_logout():
    if not settings.oidc_enabled:
        raise HTTPException(status_code=404, detail="OIDC not enabled")
    issuer = settings.oidc_issuer_url.rstrip("/")
    frontend = settings.oidc_redirect_uri.rsplit("/auth/callback", 1)[0] or "http://localhost:5173"
    url = (
        f"{issuer}/protocol/openid-connect/logout"
        f"?post_logout_redirect_uri={frontend}"
    )
    return RedirectResponse(url)


async def _fetch_oidc_profile(code: str) -> tuple[dict, str]:
    issuer = settings.oidc_issuer_url.rstrip("/")
    token_url = f"{issuer}/protocol/openid-connect/token"
    userinfo_url = f"{issuer}/protocol/openid-connect/userinfo"
    async with httpx.AsyncClient(timeout=30.0) as client:
        r = await client.post(
            token_url,
            data={
                "grant_type": "authorization_code",
                "code": code,
                "client_id": settings.oidc_client_id,
                "client_secret": settings.oidc_client_secret,
                "redirect_uri": settings.oidc_redirect_uri,
            },
        )
        if r.status_code != 200:
            raise HTTPException(status_code=400, detail="OIDC token exchange failed")
        tokens = r.json()
        access = tokens.get("access_token")
        if not access:
            raise HTTPException(status_code=400, detail="OIDC access token missing")
        ui = await client.get(userinfo_url, headers={"Authorization": f"Bearer {access}"})
        if ui.status_code != 200:
            raise HTTPException(status_code=400, detail="OIDC userinfo failed")
        profile = ui.json()
    email = profile.get("email") or profile.get("preferred_username")
    if not email:
        raise HTTPException(status_code=400, detail="OIDC profile missing email")
    groups = profile.get("groups") or profile.get("roles") or []
    if isinstance(groups, str):
        groups = [groups]
    return {
        "email": email.lower(),
        "sub": profile.get("sub"),
        "groups": groups,
        "org_slug": profile.get("org_slug"),
        "org_name": profile.get("organization"),
    }, access


async def _resolve_org_from_claims(db: AsyncSession, profile: dict) -> Organization:
    settings_map = {}
    org_slug = profile.get("org_slug")
    if org_slug:
        result = await db.execute(select(Organization).where(Organization.slug == org_slug))
        org = result.scalar_one_or_none()
        if org:
            return org
    return await resolve_org_for_sso(db, org_slug=None, org_name=profile.get("org_name"))

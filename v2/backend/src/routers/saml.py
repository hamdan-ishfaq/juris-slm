"""Phase 9C — SAML 2.0 Service Provider endpoints."""
from __future__ import annotations

from fastapi import APIRouter, Depends, Form, HTTPException
from fastapi.responses import RedirectResponse, Response
from sqlalchemy.ext.asyncio import AsyncSession

from auth_utils import create_access_token
from config import settings
from db import get_db
from routers.auth import _user_response
from services.rls import set_rls_org_context
from services.saml_sp import build_authn_request_redirect_url, build_sp_metadata_xml, parse_saml_response
from services.sso_provision import provision_sso_user, resolve_org_for_sso

router = APIRouter(prefix="/api/v1/auth/saml", tags=["saml"])


@router.get("/metadata")
async def saml_metadata():
    if not settings.saml_enabled:
        raise HTTPException(status_code=404, detail="SAML not enabled")
    return Response(content=build_sp_metadata_xml(), media_type="application/xml")


@router.get("/login")
async def saml_login():
    if not settings.saml_enabled:
        raise HTTPException(status_code=404, detail="SAML not enabled")
    try:
        url = build_authn_request_redirect_url()
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return RedirectResponse(url)


@router.post("/acs")
async def saml_acs(
    SAMLResponse: str = Form(...),
    db: AsyncSession = Depends(get_db),
):
    if not settings.saml_enabled:
        raise HTTPException(status_code=404, detail="SAML not enabled")
    try:
        profile = parse_saml_response(SAMLResponse)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    org = await resolve_org_for_sso(db, org_slug=None, org_name=None)
    user = await provision_sso_user(
        db,
        email=profile["email"],
        external_id=profile.get("external_id"),
        idp_source="saml",
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
async def saml_logout():
    if not settings.saml_enabled:
        raise HTTPException(status_code=404, detail="SAML not enabled")
    frontend = settings.oidc_redirect_uri.rsplit("/auth/callback", 1)[0] or "http://localhost:5173"
    return RedirectResponse(frontend)

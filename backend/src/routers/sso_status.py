"""Public SSO status for login page."""
from __future__ import annotations

from fastapi import APIRouter

from config import settings

router = APIRouter(prefix="/api/v1/auth", tags=["auth"])


@router.get("/sso/status")
async def sso_status():
    return {
        "oidc_enabled": settings.oidc_enabled,
        "saml_enabled": settings.saml_enabled,
        "oidc_login_url": "/api/v1/auth/oidc/login" if settings.oidc_enabled else None,
        "saml_login_url": "/api/v1/auth/saml/login" if settings.saml_enabled else None,
    }

from uuid import UUID

import asyncio
import json
import subprocess
import sys
import uuid
from datetime import datetime, timezone
from pathlib import Path

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from config import settings
from db import Organization, User, get_db
from deps import require_role
from schemas import AdminRoleUpdateRequest, AdminUserResponse
from services.access_control import admin_role_at_least

router = APIRouter(prefix="/api/v1/admin", tags=["admin"])

V2_ROOT = Path(__file__).resolve().parents[3]
REPORTS = V2_ROOT / "eval" / "reports"
_EVAL_LOCK = asyncio.Lock()
_EVAL_STATUS: dict = {"running": False, "last_run": None, "log": []}


class EvalRunResponse(BaseModel):
    status: str
    message: str


class OrgResponse(BaseModel):
    id: UUID
    name: str
    slug: str | None
    settings: dict


class OrgUpdateRequest(BaseModel):
    name: str | None = None
    settings: dict | None = None


class SsoSettingsResponse(BaseModel):
    oidc_enabled: bool
    saml_enabled: bool
    scim_enabled: bool
    oidc_issuer_url: str
    oidc_redirect_uri: str
    saml_entity_id: str
    saml_acs_url: str
    saml_metadata_url: str
    idp_group_role_map: dict


class ScimTokenResponse(BaseModel):
    token: str
    label: str


def _append_eval_log(line: str) -> None:
    _EVAL_STATUS["log"].append(f"{datetime.now(timezone.utc).isoformat()} {line}")
    _EVAL_STATUS["log"] = _EVAL_STATUS["log"][-200:]


async def _run_eval_suite() -> None:
    global _EVAL_STATUS
    if settings.environment == "production":
        return
    async with _EVAL_LOCK:
        _EVAL_STATUS["running"] = True
        _EVAL_STATUS["last_run"] = None
        _EVAL_STATUS["log"] = []
        py = sys.executable
        scripts = [
            ([py, str(V2_ROOT / "scripts" / "run_logical_eval.py"), "--offline"], "offline logical"),
            ([py, str(V2_ROOT / "scripts" / "run_logical_eval.py")], "API logical"),
            ([py, str(V2_ROOT / "scripts" / "run_ragas_eval.py")], "RAGAS proxy"),
            ([py, str(V2_ROOT / "scripts" / "run_native_ragas.py")], "native RAGAS"),
            ([py, str(V2_ROOT / "scripts" / "run_latency_bench.py")], "latency"),
        ]
        for cmd, label in scripts:
            _append_eval_log(f"START {label}")
            try:
                proc = await asyncio.create_subprocess_exec(
                    *cmd,
                    cwd=str(V2_ROOT),
                    stdout=subprocess.PIPE,
                    stderr=subprocess.STDOUT,
                )
                out, _ = await proc.communicate()
                for line in (out or b"").decode(errors="replace").splitlines()[-5:]:
                    _append_eval_log(line)
                _append_eval_log(f"END {label} exit={proc.returncode}")
            except Exception as exc:
                _append_eval_log(f"FAIL {label}: {exc}")
        _EVAL_STATUS["running"] = False
        _EVAL_STATUS["last_run"] = datetime.now(timezone.utc).isoformat()


@router.post("/run-eval", response_model=EvalRunResponse)
async def run_eval_suite(
    background: BackgroundTasks,
    user: User = Depends(require_role("org_admin", "owner")),
):
    if settings.environment == "production":
        raise HTTPException(status_code=403, detail="Eval runner disabled in production")
    if _EVAL_STATUS.get("running"):
        return EvalRunResponse(status="running", message="Eval suite already in progress")
    background.add_task(_run_eval_suite)
    return EvalRunResponse(status="started", message="Eval suite started in background")


@router.get("/eval-status")
async def eval_status(user: User = Depends(require_role("org_admin", "owner"))):
    if settings.environment == "production":
        raise HTTPException(status_code=403, detail="Eval status disabled in production")
    metrics = {}
    for name, path in [
        ("logical", REPORTS / "logical_latest.json"),
        ("ragas", REPORTS / "ragas_latest.json"),
        ("ragas_native", REPORTS / "ragas_native_latest.json"),
        ("latency", REPORTS / "latency_latest.json"),
    ]:
        if path.is_file():
            try:
                metrics[name] = json.loads(path.read_text(encoding="utf-8"))
            except (json.JSONDecodeError, OSError):
                metrics[name] = None
    return {**_EVAL_STATUS, "reports": metrics}


@router.get("/users", response_model=list[AdminUserResponse])
async def list_users(
    user: User = Depends(require_role("org_admin", "owner")),
    db: AsyncSession = Depends(get_db),
):
    query = select(User)
    if user.org_id:
        query = query.where(User.org_id == user.org_id)
    result = await db.execute(query.order_by(User.created_at))
    return [
        AdminUserResponse(
            id=u.id,
            email=u.email,
            role=u.role,
            org_id=u.org_id,
            created_at=u.created_at,
        )
        for u in result.scalars().all()
    ]


@router.put("/users/{user_id}/role", response_model=AdminUserResponse)
async def update_user_role(
    user_id: UUID,
    body: AdminRoleUpdateRequest,
    actor: User = Depends(require_role("owner")),
    db: AsyncSession = Depends(get_db),
):
    target = await db.get(User, user_id)
    if not target:
        raise HTTPException(status_code=404, detail="User not found")
    if actor.org_id and target.org_id and actor.org_id != target.org_id:
        raise HTTPException(status_code=403, detail="Cannot modify users outside your organization")
    if target.id == actor.id:
        raise HTTPException(status_code=400, detail="Cannot change your own role")
    if body.role == "owner":
        raise HTTPException(status_code=400, detail="Owner role cannot be assigned via API")
    if not admin_role_at_least(body.role, "member"):
        raise HTTPException(status_code=400, detail="Invalid role")

    target.role = body.role
    await db.commit()
    await db.refresh(target)
    return AdminUserResponse(
        id=target.id,
        email=target.email,
        role=target.role,
        org_id=target.org_id,
        created_at=target.created_at,
    )


@router.delete("/users/{user_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_user(
    user_id: UUID,
    actor: User = Depends(require_role("owner")),
    db: AsyncSession = Depends(get_db),
):
    target = await db.get(User, user_id)
    if not target:
        raise HTTPException(status_code=404, detail="User not found")
    if actor.org_id and target.org_id and actor.org_id != target.org_id:
        raise HTTPException(status_code=403, detail="Cannot delete users outside your organization")
    if target.id == actor.id:
        raise HTTPException(status_code=400, detail="Cannot delete yourself")
    await db.delete(target)
    await db.commit()


@router.get("/org", response_model=OrgResponse)
async def get_org(
    user: User = Depends(require_role("org_admin", "owner")),
    db: AsyncSession = Depends(get_db),
):
    if not user.org_id:
        raise HTTPException(status_code=404, detail="Organization not found")
    org = await db.get(Organization, user.org_id)
    if not org:
        raise HTTPException(status_code=404, detail="Organization not found")
    return OrgResponse(id=org.id, name=org.name, slug=org.slug, settings=org.settings or {})


@router.patch("/org", response_model=OrgResponse)
async def update_org(
    body: OrgUpdateRequest,
    user: User = Depends(require_role("org_admin", "owner")),
    db: AsyncSession = Depends(get_db),
):
    if not user.org_id:
        raise HTTPException(status_code=404, detail="Organization not found")
    org = await db.get(Organization, user.org_id)
    if not org:
        raise HTTPException(status_code=404, detail="Organization not found")
    if body.name is not None:
        name = body.name.strip()
        if not name:
            raise HTTPException(status_code=400, detail="Organization name cannot be empty")
        org.name = name
    if body.settings is not None:
        org.settings = {**(org.settings or {}), **body.settings}
    await db.commit()
    await db.refresh(org)
    return OrgResponse(id=org.id, name=org.name, slug=org.slug, settings=org.settings or {})


@router.get("/sso", response_model=SsoSettingsResponse)
async def get_sso_settings(
    user: User = Depends(require_role("org_admin", "owner")),
    db: AsyncSession = Depends(get_db),
):
    org_settings: dict = {}
    if user.org_id:
        org = await db.get(Organization, user.org_id)
        if org:
            org_settings = org.settings or {}
    return SsoSettingsResponse(
        oidc_enabled=settings.oidc_enabled,
        saml_enabled=settings.saml_enabled,
        scim_enabled=settings.scim_enabled,
        oidc_issuer_url=settings.oidc_issuer_url,
        oidc_redirect_uri=settings.oidc_redirect_uri,
        saml_entity_id=settings.saml_entity_id,
        saml_acs_url=settings.saml_acs_url,
        saml_metadata_url="/api/v1/auth/saml/metadata",
        idp_group_role_map=(org_settings.get("idp_group_role_map") or {}),
    )


@router.post("/scim-token", response_model=ScimTokenResponse)
async def create_scim_token(
    user: User = Depends(require_role("org_admin", "owner")),
    db: AsyncSession = Depends(get_db),
):
    if not user.org_id:
        raise HTTPException(status_code=400, detail="User must belong to an organization")
    from db import ScimToken
    from services.scim_auth import generate_scim_token, hash_scim_token

    raw = generate_scim_token()
    token = ScimToken(
        id=uuid.uuid4(),
        org_id=user.org_id,
        token_hash=hash_scim_token(raw),
        label="admin-generated",
        created_by=user.id,
    )
    db.add(token)
    await db.commit()
    return ScimTokenResponse(token=raw, label=token.label)


@router.post("/users/{user_id}/revoke-sessions")
async def revoke_user_sessions(
    user_id: UUID,
    user: User = Depends(require_role("org_admin", "owner")),
    db: AsyncSession = Depends(get_db),
):
    if not user.org_id:
        raise HTTPException(status_code=400, detail="User must belong to an organization")
    target = await db.get(User, user_id)
    if not target or target.org_id != user.org_id:
        raise HTTPException(status_code=404, detail="User not found")
    from services.refresh_token import revoke_user_sessions as _revoke

    count = await _revoke(db, user_id)
    await db.commit()
    return {"ok": True, "revoked": count}

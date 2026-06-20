"""Phase 9C — SSO user provisioning and org resolution."""
from __future__ import annotations

import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from auth_utils import hash_password
from db import Organization, User, slugify_org_name
from services.idp_groups import map_groups_to_role


async def resolve_org_for_sso(
    db: AsyncSession,
    *,
    org_slug: str | None,
    org_name: str | None,
) -> Organization:
    if org_slug:
        result = await db.execute(select(Organization).where(Organization.slug == org_slug))
        org = result.scalar_one_or_none()
        if org:
            return org
    if org_name:
        base = slugify_org_name(org_name)
        slug = base
        suffix = 0
        while True:
            clash = await db.execute(select(Organization).where(Organization.slug == slug))
            if not clash.scalar_one_or_none():
                break
            suffix += 1
            slug = f"{base}-{suffix}"[:64]
        org = Organization(id=uuid.uuid4(), name=org_name.strip(), slug=slug)
        db.add(org)
        await db.flush()
        return org

    result = await db.execute(select(Organization).where(Organization.slug == "default-org"))
    org = result.scalar_one_or_none()
    if org:
        return org
    org = Organization(name="Default Organization", slug="default-org")
    db.add(org)
    await db.flush()
    return org


async def provision_sso_user(
    db: AsyncSession,
    *,
    email: str,
    external_id: str | None,
    idp_source: str,
    groups: list[str] | None,
    org: Organization,
    display_name: str | None = None,
) -> User:
    email = email.lower().strip()
    result = await db.execute(select(User).where(User.email == email))
    user = result.scalar_one_or_none()
    role = map_groups_to_role(groups, org.settings)

    if user:
        user.org_id = org.id
        user.external_id = external_id or user.external_id
        user.idp_source = idp_source
        user.disabled_at = None
        if user.role != "owner":
            user.role = role
        await db.flush()
        return user

    user = User(
        id=uuid.uuid4(),
        email=email,
        password_hash="sso-only",
        role=role,
        org_id=org.id,
        external_id=external_id,
        idp_source=idp_source,
    )
    db.add(user)
    await db.flush()
    return user


def password_login_allowed(org_settings: dict | None) -> bool:
    settings = org_settings or {}
    if settings.get("password_login_disabled") is True:
        return False
    return True

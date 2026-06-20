"""Dev master user — local eval/E2E only; rate-limit bypass via verified user id."""
from __future__ import annotations

import logging
import uuid

from fastapi import Request
from sqlalchemy import select

from auth_utils import decode_token, hash_password
from config import settings
from db import Organization, User, async_session_factory

logger = logging.getLogger(__name__)

_dev_master_user_id: str | None = None


def get_dev_master_user_id() -> str | None:
    return _dev_master_user_id


def is_dev_master_email(email: str) -> bool:
    if not settings.dev_master_enabled or not settings.dev_master_email:
        return False
    return email.lower().strip() == settings.dev_master_email.lower().strip()


def is_dev_master_user_id(user_id: str | None) -> bool:
    if not settings.dev_master_enabled or not user_id or not _dev_master_user_id:
        return False
    return str(user_id) == _dev_master_user_id


def token_extra_for_user(email: str) -> dict:
    """No bypass claims in JWT — exemption verified server-side by user id."""
    if is_dev_master_email(email):
        return {"dev_master": True}
    return {}


def is_rate_limit_exempt(request: Request) -> bool:
    """SlowAPI exempt_when — only the seeded dev master user id, not JWT claims."""
    if not settings.dev_master_enabled or not _dev_master_user_id:
        return False
    auth = request.headers.get("Authorization", "")
    if not auth.lower().startswith("bearer "):
        return False
    try:
        payload = decode_token(auth[7:].strip())
    except ValueError:
        return False
    return payload.get("sub") == _dev_master_user_id


async def ensure_dev_master_user() -> None:
    """Create or update the dev master user on API startup."""
    global _dev_master_user_id

    if not settings.dev_master_enabled:
        _dev_master_user_id = None
        return
    if not settings.dev_master_email or not settings.dev_master_password:
        logger.warning("DEV_MASTER enabled but email/password missing — skipping seed")
        return

    email = settings.dev_master_email.lower().strip()
    async with async_session_factory() as db:
        org_res = await db.execute(select(Organization).where(Organization.slug == "default-org"))
        org = org_res.scalar_one_or_none()
        if org is None:
            org = Organization(name="Default Organization", slug="default-org")
            db.add(org)
            await db.flush()

        user_res = await db.execute(select(User).where(User.email == email))
        user = user_res.scalar_one_or_none()
        pwd_hash = hash_password(settings.dev_master_password)
        if user is None:
            user = User(
                email=email,
                password_hash=pwd_hash,
                role="owner",
                org_id=org.id,
            )
            db.add(user)
            await db.flush()
            logger.info("Dev master account seeded (owner role)")
        else:
            user.password_hash = pwd_hash
            user.role = "owner"
            user.org_id = org.id
            logger.info("Dev master account updated")
        _dev_master_user_id = str(user.id)
        await db.commit()

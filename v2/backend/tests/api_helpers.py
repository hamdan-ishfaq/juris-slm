"""Shared HTTP + DB helpers for Phase 1 integration tests."""
from __future__ import annotations

import os
import time
import uuid
from typing import Any

import httpx
import redis
from sqlalchemy import select

from db import Organization, async_session_factory

API_BASE = os.environ.get("JURIS_API_BASE", "http://localhost:8002")
DEFAULT_PASSWORD = "SecureTestPass123!"
REDIS_URL = os.environ.get("REDIS_URL", "redis://localhost:6380/0")


def clear_rate_limits() -> int:
    """Remove SlowAPI limiter keys so integration tests do not trip prior windows."""
    client = redis.from_url(REDIS_URL)
    deleted = 0
    for key in client.scan_iter("LIMITS:LIMITER*"):
        client.delete(key)
        deleted += 1
    return deleted


def api_reachable() -> bool:
    try:
        r = httpx.get(f"{API_BASE}/health", timeout=5.0)
        return r.status_code == 200
    except httpx.HTTPError:
        return False


def register_user(
    email: str | None = None,
    *,
    password: str = DEFAULT_PASSWORD,
    org_name: str | None = None,
    max_attempts: int = 8,
) -> dict[str, Any]:
    email = email or f"test_{uuid.uuid4().hex[:10]}@example.com"
    body: dict[str, Any] = {"email": email, "password": password}
    if org_name:
        body["org_name"] = org_name
    last: httpx.Response | None = None
    for attempt in range(max_attempts):
        r = httpx.post(f"{API_BASE}/api/v1/auth/register", json=body, timeout=30.0)
        last = r
        if r.status_code != 429:
            break
        time.sleep(min(2**attempt, 15))
    assert last is not None
    last.raise_for_status()
    data = last.json()
    user = data.get("user") or {}
    return {
        "email": email,
        "password": password,
        "token": data["access_token"],
        "user_id": user.get("id") or _me_user_id(data["access_token"]),
        "role": user.get("role", "member"),
        "org_id": user.get("org_id"),
    }


def login_user(email: str, password: str = DEFAULT_PASSWORD) -> str:
    r = httpx.post(
        f"{API_BASE}/api/v1/auth/login",
        json={"email": email, "password": password},
        timeout=30.0,
    )
    r.raise_for_status()
    return r.json()["access_token"]


def _me_user_id(token: str) -> str:
    r = httpx.get(
        f"{API_BASE}/api/v1/auth/me",
        headers={"Authorization": f"Bearer {token}"},
        timeout=15.0,
    )
    r.raise_for_status()
    return str(r.json()["id"])


def api_request(
    method: str,
    path: str,
    *,
    token: str | None = None,
    json_body: dict | None = None,
    files: dict | None = None,
    data: dict | None = None,
    timeout: float = 120.0,
) -> httpx.Response:
    headers: dict[str, str] = {}
    if token:
        headers["Authorization"] = f"Bearer {token}"
    return httpx.request(
        method,
        f"{API_BASE}{path}",
        headers=headers,
        json=json_body,
        files=files,
        data=data,
        timeout=timeout,
    )


async def assign_user_to_org(user_id: str, org_id: str) -> None:
    """Test setup: place user in same org as owner for member-invite flows."""
    assign_user_to_org_sync(user_id, org_id)


def assign_user_to_org_sync(user_id: str, org_id: str) -> None:
    """Sync DB update — avoids asyncio event-loop conflicts in pytest."""
    import psycopg

    db_url = os.environ.get("DATABASE_URL", "postgresql+asyncpg://juris:juris_password@localhost:5433/juris_db")
    sync_url = db_url.replace("postgresql+asyncpg://", "postgresql://")
    with psycopg.connect(sync_url) as conn:
        with conn.cursor() as cur:
            cur.execute(
                "UPDATE users SET org_id = %s WHERE id = %s",
                (org_id, user_id),
            )
        conn.commit()


async def get_org_id_by_slug(slug: str) -> uuid.UUID | None:
    async with async_session_factory() as db:
        result = await db.execute(select(Organization.id).where(Organization.slug == slug))
        return result.scalar_one_or_none()

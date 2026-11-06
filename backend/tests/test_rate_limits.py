"""Rate limit integration tests — Phase 1."""
from __future__ import annotations

import uuid

import httpx
import pytest

from api_helpers import API_BASE, register_user


@pytest.mark.integration
def test_login_rate_limit_returns_429(api_up):
    email = f"ratelimit_{uuid.uuid4().hex[:8]}@example.com"
    register_user(email)

    got_429 = False
    for i in range(8):
        r = httpx.post(
            f"{API_BASE}/api/v1/auth/login",
            json={"email": email, "password": "wrong-password"},
            timeout=10.0,
        )
        if r.status_code == 429:
            got_429 = True
            break
    assert got_429, "Expected 429 after burst login attempts (limit 5/min)"

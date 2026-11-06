"""Security tests for dev master rate-limit bypass."""
from __future__ import annotations

from unittest.mock import MagicMock

from auth_utils import create_access_token
from fastapi import Request
from services.dev_master import (
    get_dev_master_user_id,
    is_dev_master_user_id,
    is_rate_limit_exempt,
    token_extra_for_user,
)
from config import settings


def test_dev_master_email_match():
    assert settings.dev_master_email


def test_dev_master_token_extra_no_bypass_claim():
    extra = token_extra_for_user(settings.dev_master_email)
    assert "rate_limit_bypass" not in extra
    assert extra.get("dev_master") is True


def test_rate_limit_exempt_only_for_seeded_user_id():
    dev_id = get_dev_master_user_id()
    if not dev_id:
        return  # dev master disabled in test env
    token = create_access_token(dev_id, extra={"role": "owner"})
    request = MagicMock(spec=Request)
    request.headers = {"Authorization": f"Bearer {token}"}
    assert is_rate_limit_exempt(request) is True


def test_forged_bypass_claim_not_enough():
    """JWT with fake bypass claim but wrong sub must not exempt."""
    token = create_access_token(
        "00000000-0000-0000-0000-000000000099",
        extra={"rate_limit_bypass": True, "dev_master": True, "role": "owner"},
    )
    request = MagicMock(spec=Request)
    request.headers = {"Authorization": f"Bearer {token}"}
    assert is_rate_limit_exempt(request) is False


def test_is_dev_master_user_id_helper():
    dev_id = get_dev_master_user_id()
    if dev_id:
        assert is_dev_master_user_id(dev_id) is True
    assert is_dev_master_user_id("not-a-real-id") is False

"""Production configuration validation tests."""
from __future__ import annotations

import pytest

from config import Settings
from services.config_security import validate_settings


def test_production_rejects_dev_master(monkeypatch):
    monkeypatch.setenv("ENVIRONMENT", "production")
    monkeypatch.setenv("DEV_MASTER_ENABLED", "true")
    monkeypatch.setenv("AUTH_SECRET_KEY", "a" * 40)
    monkeypatch.setenv("REGISTRATION_OPEN", "false")
    monkeypatch.setenv("EXPOSE_OPENAPI", "false")
    cfg = Settings()
    with pytest.raises(RuntimeError, match="DEV_MASTER"):
        validate_settings(cfg)


def test_production_rejects_weak_secret(monkeypatch):
    monkeypatch.setenv("ENVIRONMENT", "production")
    monkeypatch.setenv("DEV_MASTER_ENABLED", "false")
    monkeypatch.setenv("AUTH_SECRET_KEY", "change-me-in-production")
    monkeypatch.setenv("REGISTRATION_OPEN", "false")
    monkeypatch.setenv("EXPOSE_OPENAPI", "false")
    cfg = Settings()
    with pytest.raises(RuntimeError, match="AUTH_SECRET_KEY"):
        validate_settings(cfg)


def test_development_allows_local_defaults(monkeypatch):
    monkeypatch.setenv("ENVIRONMENT", "development")
    monkeypatch.setenv("DEV_MASTER_ENABLED", "true")
    monkeypatch.setenv("AUTH_SECRET_KEY", "dev-secret-change-in-prod")
    cfg = Settings()
    validate_settings(cfg)

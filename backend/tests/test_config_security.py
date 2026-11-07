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


def _production(monkeypatch, **env):
    base = {"ENVIRONMENT": "production", "DEV_MASTER_ENABLED": "false", "AUTH_SECRET_KEY": "s" * 40,
            "REGISTRATION_OPEN": "false", "EXPOSE_OPENAPI": "false", "LLM_PROVIDER": "ollama", "OPENROUTER_API_KEY": ""}
    for key, value in {**base, **env}.items():
        monkeypatch.setenv(key, value)
    monkeypatch.delenv("OTEL_EXPORTER_OTLP_ENDPOINT", raising=False)


def test_production_on_ollama_rejects_a_cloud_api_key(monkeypatch):
    _production(monkeypatch, OPENROUTER_API_KEY="sk-or-v1-abc")
    with pytest.raises(RuntimeError, match="OPENROUTER_API_KEY"):
        validate_settings(Settings())


def test_production_rejects_a_public_tracing_host(monkeypatch):
    _production(monkeypatch)
    monkeypatch.setenv("OTEL_EXPORTER_OTLP_ENDPOINT", "https://otlp.example-cloud.com:4318")
    with pytest.raises(RuntimeError, match="OTEL_EXPORTER_OTLP_ENDPOINT"):
        validate_settings(Settings())


def test_production_allows_a_local_tracing_collector(monkeypatch):
    for endpoint in ("http://jaeger:4318", "http://10.0.0.5:4318", "http://localhost:4318"):
        _production(monkeypatch)
        monkeypatch.setenv("OTEL_EXPORTER_OTLP_ENDPOINT", endpoint)
        validate_settings(Settings())

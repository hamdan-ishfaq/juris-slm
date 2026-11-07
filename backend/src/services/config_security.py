"""Production safety checks — fail fast on insecure defaults."""
from __future__ import annotations

import ipaddress
import os
from urllib.parse import urlparse

from config import Settings, settings as _settings

_WEAK_SECRETS = frozenset(
    {
        "change-me-in-production",
        "your-secret-key-change-in-production",
        "dev-secret-change-in-prod",
        "generate-a-long-random-secret-key-here",
        "secret",
        "changeme",
    }
)


def _is_local_host(url: str) -> bool:
    """A service name without dots, localhost, or a private address."""
    host = urlparse(url).hostname or ""
    if host == "localhost" or "." not in host:
        return True
    try:
        return ipaddress.ip_address(host).is_private
    except ValueError:
        return False


def validate_settings(cfg: Settings | None = None) -> None:
    """Raise RuntimeError if production-unsafe configuration is detected."""
    s = cfg or _settings
    errors: list[str] = []

    secret = s.auth_secret_key.strip()

    if s.is_production:
        if s.dev_master_enabled:
            errors.append("DEV_MASTER_ENABLED must be false when ENVIRONMENT=production")
        if s.registration_open:
            errors.append("REGISTRATION_OPEN should be false in production")
        if s.expose_openapi:
            errors.append("EXPOSE_OPENAPI should be false in production")
        if len(secret) < 32:
            errors.append("AUTH_SECRET_KEY must be at least 32 characters in production")
        if secret.lower() in _WEAK_SECRETS:
            errors.append("AUTH_SECRET_KEY is a known weak/default value")
        if s.dev_master_enabled and s.dev_master_password in (
            "DevMasterPass123!",
            "password",
            "changeme",
        ):
            errors.append("DEV_MASTER_PASSWORD is too weak for production-like environments")

        # An offline deployment must not hold a cloud key or send traces off the network.
        if s.llm_provider == "ollama" and s.openrouter_api_key.strip():
            errors.append("OPENROUTER_API_KEY must be empty when LLM_PROVIDER=ollama in production")
        endpoint = os.environ.get("OTEL_EXPORTER_OTLP_ENDPOINT", "")
        if endpoint and not _is_local_host(endpoint):
            errors.append("OTEL_EXPORTER_OTLP_ENDPOINT must point at a collector on the local network in production")

    if errors:
        raise RuntimeError("Insecure configuration:\n  - " + "\n  - ".join(errors))


def is_admin_role(role: str) -> bool:
    return role in ("org_admin", "owner")

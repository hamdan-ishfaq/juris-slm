"""Integration test: hybrid FTS column exists and returns hits (Phase 2.1)."""
from __future__ import annotations

import pytest

from api_helpers import api_reachable, register_user, api_request


@pytest.mark.integration
def test_status_reports_phase2_retrieval(api_up):
    import httpx
    from api_helpers import API_BASE

    r = httpx.get(f"{API_BASE}/health", timeout=10)
    assert r.status_code == 200
    assert r.json().get("phase") == "phase-2-retrieval"

    r = httpx.get(f"{API_BASE}/api/v1/status", timeout=10)
    data = r.json()
    assert data.get("phase") == "phase-2-retrieval"
    retrieval = data.get("retrieval") or {}
    assert retrieval.get("hybrid_search") is True


@pytest.mark.integration
def test_chat_hybrid_law_corpus(api_up):
    user = register_user()
    r = api_request(
        "POST",
        "/api/v1/chat",
        token=user["token"],
        json_body={"message": "What is lawful processing under GDPR Article 6?", "use_law_corpus": True},
        timeout=180.0,
    )
    assert r.status_code == 200
    data = r.json()
    assert len(data.get("answer", "")) > 20
    assert isinstance(data.get("sources"), list)

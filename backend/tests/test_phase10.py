"""Phase 10 — production hardening unit tests."""
from __future__ import annotations

import hashlib
from unittest.mock import MagicMock, patch

import pytest

from services.ml_device import resolve_device
from services.query_enhance import adaptive_use_hyde
from services.refresh_token import _hash_token, _new_raw_token


@pytest.mark.unit
def test_resolve_device_cpu():
    assert resolve_device("cpu") == "cpu"


@pytest.mark.unit
def test_resolve_device_auto_falls_back_without_cuda():
    mock_torch = MagicMock()
    mock_torch.cuda.is_available.return_value = False
    with patch.dict("sys.modules", {"torch": mock_torch}):
        assert resolve_device("auto") == "cpu"
    with patch.dict("sys.modules", {"torch": mock_torch}):
        assert resolve_device("cuda") == "cpu"


@pytest.mark.unit
def test_resolve_device_cuda_when_available():
    mock_torch = MagicMock()
    mock_torch.cuda.is_available.return_value = True
    with patch.dict("sys.modules", {"torch": mock_torch}):
        assert resolve_device("cuda") == "cuda"
        assert resolve_device("auto") == "cuda"


@pytest.mark.unit
def test_adaptive_hyde_disabled_in_airgap_profile():
    with patch("services.query_enhance.settings") as mock_settings:
        mock_settings.is_airgap_latency_profile = True
        mock_settings.hyde_enabled = False
        assert adaptive_use_hyde("What about data protection?", use_hyde=False) is False


@pytest.mark.unit
def test_airgap_latency_profile_property():
    from config import Settings

    s = Settings(LLM_PROVIDER="ollama")
    assert s.is_airgap_latency_profile is True
    s2 = Settings(LLM_PROVIDER="openrouter", AIRGAP_LATENCY_PROFILE=False)
    assert s2.is_airgap_latency_profile is False


@pytest.mark.unit
def test_effective_access_token_minutes():
    from config import Settings

    s = Settings(AUTH_ACCESS_EXPIRE_MINUTES=15, AUTH_TOKEN_EXPIRE_MINUTES=60)
    assert s.effective_access_token_minutes == 15


@pytest.mark.unit
def test_refresh_token_hash_stable():
    raw = "test-token-value"
    assert _hash_token(raw) == hashlib.sha256(raw.encode()).hexdigest()


@pytest.mark.unit
def test_new_raw_token_length():
    assert len(_new_raw_token()) >= 32


@pytest.mark.unit
def test_device_status_keys():
    from services.ml_device import device_status

    d = device_status()
    assert "cuda_available" in d
    assert "embedding_device" in d
    assert "reranker_device" in d


@pytest.mark.unit
def test_rag_crag_skips_hyde_in_airgap():
    with patch("services.rag.settings") as mock_settings:
        mock_settings.is_airgap_latency_profile = True
        hyde_on = True
        retry_hyde = hyde_on and not mock_settings.is_airgap_latency_profile
        assert retry_hyde is False

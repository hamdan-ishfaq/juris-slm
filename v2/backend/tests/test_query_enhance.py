"""Tests for legal query enhancement."""
from services.query_enhance import adaptive_use_hyde, crag_rewrite_query, expand_legal_query


def test_expand_legal_query_article():
    out = expand_legal_query("What is Article 6 GDPR?")
    assert "Art. 6" in out or "Article 6" in out


def test_adaptive_hyde_vague(monkeypatch):
    """Adaptive HyDE must not depend on air-gap profile (CI runs with LLM_PROVIDER=ollama)."""
    monkeypatch.setattr("services.query_enhance.settings.adaptive_hyde_enabled", True)
    monkeypatch.setattr("services.query_enhance.settings.hyde_enabled", False)
    monkeypatch.setattr("services.query_enhance.settings.airgap_latency_profile", False)
    assert adaptive_use_hyde("What about data protection?", use_hyde=False) is True


def test_adaptive_hyde_explicit_article(monkeypatch):
    monkeypatch.setattr("services.query_enhance.settings.adaptive_hyde_enabled", True)
    monkeypatch.setattr("services.query_enhance.settings.hyde_enabled", False)
    monkeypatch.setattr("services.query_enhance.settings.airgap_latency_profile", False)
    assert adaptive_use_hyde("Explain Article 28 processor rules", use_hyde=False) is False


def test_crag_rewrite_adds_context():
    out = crag_rewrite_query("processor obligations")
    assert "processor" in out.lower()

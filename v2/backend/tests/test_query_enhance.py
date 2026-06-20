"""Tests for legal query enhancement."""
from services.query_enhance import adaptive_use_hyde, crag_rewrite_query, expand_legal_query


def test_expand_legal_query_article():
    out = expand_legal_query("What is Article 6 GDPR?")
    assert "Art. 6" in out or "Article 6" in out


def test_adaptive_hyde_vague():
    assert adaptive_use_hyde("What about data protection?", use_hyde=False) is True


def test_adaptive_hyde_explicit_article():
    assert adaptive_use_hyde("Explain Article 28 processor rules", use_hyde=False) is False


def test_crag_rewrite_adds_context():
    out = crag_rewrite_query("processor obligations")
    assert "processor" in out.lower()

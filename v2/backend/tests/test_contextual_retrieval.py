"""Unit tests for contextual retrieval prefixes (Phase 2.4)."""
from __future__ import annotations

from services.contextual_retrieval import build_embedding_text


def test_law_context_prefix():
    text = build_embedding_text(
        "Personal data must be processed lawfully.",
        {"kind": "law", "title": "GDPR (English)", "article": "6", "source": "gdpr"},
    )
    assert "GDPR" in text
    assert "Article 6" in text
    assert "Personal data" in text


def test_contract_context_prefix():
    text = build_embedding_text(
        "The Receiving Party shall not disclose.",
        {"kind": "contract", "section_title": "Article 3 Confidentiality"},
    )
    assert "Confidentiality" in text
    assert "Receiving Party" in text

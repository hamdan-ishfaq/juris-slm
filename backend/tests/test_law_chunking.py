"""Unit tests for structure-aware law chunking (Phase 2.3)."""
from __future__ import annotations

from services.law_chunking import chunk_law_text


SAMPLE = """
Article 6 - Lawfulness of processing

1. Processing shall be lawful only if and to the extent that at least one of the following applies:
(a) the data subject has given consent.

Article 7 - Conditions for consent

1. Where processing is based on consent, the controller shall be able to demonstrate that the data subject has consented.
"""


def test_chunk_law_text_splits_on_articles():
    chunks = chunk_law_text(SAMPLE, source="gdpr", title="GDPR")
    assert len(chunks) >= 2
    articles = {c["metadata"].get("article") for c in chunks}
    assert "6" in articles
    assert "7" in articles


def test_chunk_law_text_preserves_content():
    chunks = chunk_law_text(SAMPLE, source="gdpr", title="GDPR")
    combined = " ".join(c["content"] for c in chunks)
    assert "Lawfulness" in combined
    assert "consent" in combined.lower()

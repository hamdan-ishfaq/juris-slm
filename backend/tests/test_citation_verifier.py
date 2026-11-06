"""Unit tests for Phase 2 citation verifier."""
from __future__ import annotations

from services.citation_verifier import extract_citations, verify_citations


def test_extract_citations_finds_article_refs():
    text = "Under Art. 6 GDPR and BGB Section 433, processing is lawful."
    cites = extract_citations(text)
    assert any("Art" in c or "GDPR" in c for c in cites)


def test_verify_citations_passes_when_in_sources():
    answer = "Processing relies on Art. 6 GDPR lawful basis."
    sources = [{"label": "GDPR Art. 6 Lawfulness", "source": "gdpr"}]
    contents = ["Article 6(1) Lawful processing of personal data..."]
    out, ok = verify_citations(answer, sources, contents)
    assert ok
    assert "could not be verified" not in out


def test_verify_citations_adds_disclaimer_on_miss():
    answer = "See Art. 99 GDPR for penalties."
    sources = [{"label": "unrelated", "source": "other"}]
    contents = ["Some unrelated contract clause."]
    out, ok = verify_citations(answer, sources, contents)
    assert not ok
    assert "could not be verified" in out

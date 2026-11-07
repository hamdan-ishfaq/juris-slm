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


def _law(source, article, text="Text."):
    return {"content": text, "metadata": {"source": source, "article": article, "title": source.upper()}}


def test_a_number_elsewhere_in_the_text_does_not_verify_an_article():
    hits = [{"content": "The fee is $99 per month.", "metadata": {}}]
    _, ok = verify_citations("Under Art. 99, the fee applies.", [], hits=hits)
    assert not ok


def test_the_cited_law_must_match_the_retrieved_article():
    hits = [_law("bgb", "6")]
    _, ok = verify_citations("Under GDPR Article 6, processing is lawful.", [], hits=hits)
    assert not ok


def test_an_article_tagged_on_a_retrieved_chunk_verifies():
    hits = [_law("gdpr", "6")]
    _, ok = verify_citations("Under GDPR Article 6(1)(f), processing is lawful.", [], hits=hits)
    assert ok


def test_a_section_in_contract_text_verifies():
    hits = [{"content": "Section 4.1 SLA Uptime. Provider shall maintain 99.9%.", "metadata": {}}]
    _, ok = verify_citations("Section 4 sets the uptime commitment.", [], hits=hits)
    assert ok


def test_a_german_section_sign_verifies_against_its_law():
    hits = [_law("bdsg", "26")]
    _, ok = verify_citations("Nach § 26 BDSG dürfen Daten verarbeitet werden.", [], hits=hits)
    assert ok

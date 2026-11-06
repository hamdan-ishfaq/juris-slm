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


def _articles(chunks):
    return [chunk["metadata"]["article"] for chunk in chunks]


def test_headers_with_leading_spaces_are_found():
    chunks = chunk_law_text(" Article 6\n\n Lawfulness of processing\n\n Processing shall be lawful.\n", source="gdpr", title="GDPR")
    assert _articles(chunks) == ["6"]
    assert chunks[-1]["metadata"]["section_title"] == "Lawfulness of processing"


def test_section_title_on_the_next_line_is_read():
    chunks = chunk_law_text("Section 437\nRights of buyer in the case of defects\n\nIf the thing is defective, the buyer may act.\n", source="bgb", title="BGB")
    assert _articles(chunks) == ["437"]
    assert chunks[0]["metadata"]["section_title"] == "Rights of buyer in the case of defects"


def test_german_section_header_without_a_dash_is_found():
    text = "§ 22 Verarbeitung besonderer Kategorien\n\nDie Verarbeitung ist zulässig.\n\n§ 26a Datenverarbeitung\n\nDaten dürfen verarbeitet werden.\n"
    chunks = chunk_law_text(text, source="bdsg", title="BDSG")
    assert _articles(chunks) == ["22", "26a"]
    assert chunks[0]["metadata"]["section_title"] == "Verarbeitung besonderer Kategorien"


def test_table_of_contents_entries_are_dropped():
    text = "§ 1 Anwendungsbereich\n§ 2 Begriffe\n\n§ 1 Anwendungsbereich\n\nDieses Gesetz gilt für alle Stellen.\n"
    chunks = chunk_law_text(text, source="bdsg", title="BDSG")
    assert _articles(chunks) == ["1"]
    assert "Dieses Gesetz gilt" in chunks[0]["content"]


def test_a_sentence_starting_with_a_section_sign_is_not_a_header():
    text = "§ 1 Anwendungsbereich\n\nDieses Gesetz gilt.\n§ 4 gilt entsprechend.\n\n§ 2 Begriffe\n\nEin Begriff.\n"
    chunks = chunk_law_text(text, source="bdsg", title="BDSG")
    assert _articles(chunks) == ["1", "2"]


def test_a_cross_reference_line_is_not_a_header():
    text = "Article 6\nLawfulness\n\nArticle 16(2) TFEU mandates the rules.\n\nArticle 7\nConsent\n\nConsent must be given.\n"
    chunks = chunk_law_text(text, source="gdpr", title="GDPR")
    assert _articles(chunks) == ["6", "7"]


def test_annex_is_not_labelled_as_the_last_article():
    text = "Article 113\nEntry into force\n\nThis Regulation shall enter into force.\n\nANNEX I\nList of laws\n\nSection A lists laws.\n"
    chunks = chunk_law_text(text, source="eu_ai_act", title="AI Act")
    assert _articles(chunks) == ["113", "Annex I"]
    assert chunks[1]["metadata"]["section_title"] == "List of laws"


def test_heading_stays_with_a_long_first_paragraph():
    text = "§ 26 Datenverarbeitung\n\n" + "Der Text ist lang. " * 80 + "\n\n§ 27 Forschung\n\nKurzer Text.\n"
    chunks = chunk_law_text(text, source="bdsg", title="BDSG")
    assert chunks[0]["content"].startswith("§ 26 Datenverarbeitung\n\nDer Text")
    assert all(len(chunk["content"]) >= 20 for chunk in chunks)


def test_long_german_title_is_a_header():
    title = "Verarbeitung personenbezogener Daten im Rahmen von nicht in die Anwendungsbereiche der Verordnung und der Richtlinie fallenden Tätigkeiten"
    chunks = chunk_law_text(f"§ 85 {title}\n\nDer Text gilt.\n", source="bdsg", title="BDSG")
    assert _articles(chunks) == ["85"]
    assert chunks[0]["metadata"]["section_title"] == title

"""Phase 9F — contract clause extraction unit tests."""
from __future__ import annotations

import pytest

from services.contract_clauses import extract_clauses


@pytest.mark.unit
def test_extract_clauses_numbered_sections():
    text = (
        "MUTUAL NON-DISCLOSURE AGREEMENT\n\n"
        "1. CONFIDENTIALITY\nReceiving Party shall not disclose.\n\n"
        "2. DATA PROCESSING\nPersonal data shall comply with GDPR Article 28.\n"
    )
    clauses = extract_clauses(text)
    assert len(clauses) >= 2
    assert any("confidential" in c["title"].lower() or "confidential" in c["text"].lower() for c in clauses)


@pytest.mark.unit
def test_extract_clauses_fallback_paragraphs():
    text = "Short agreement without headers.\n\nSecond paragraph about termination."
    clauses = extract_clauses(text)
    assert len(clauses) >= 1

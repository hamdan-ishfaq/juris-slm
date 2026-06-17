"""Unit tests for query decomposition (Phase 2.8)."""
from __future__ import annotations

from services.query_decompose import decompose_for_compare, decompose_general


def test_decompose_for_compare_adds_regulatory_angles():
    q = "Compare this NDA against regulatory baseline for deviations."
    subs = decompose_for_compare(q)
    assert q in subs
    assert len(subs) >= 2
    assert any("GDPR" in s or "deviation" in s.lower() for s in subs)


def test_decompose_general_single_short_question():
    q = "What is GDPR?"
    assert decompose_general(q) == [q]

"""Phase 9D — gap analysis unit tests."""
from __future__ import annotations

from services.agents.gap_analysis import MAX_TOOL_CALLS
from services.agents.tools import compare_clause, finalize_report


def test_compare_clause_aligned_for_confidentiality():
    obl = {"id": "obl-1", "clause_text": "Party shall keep all confidential information secure.", "topic": "confidentiality"}
    law_hits = [{"content": "appropriate security measures to protect personal data Article 32", "metadata": {"title": "GDPR Art. 32"}}]
    gap = compare_clause(obligation=obl, law_hits=law_hits)
    assert gap["severity"] in ("aligned", "partial")


def test_finalize_report_structure():
    report = finalize_report(
        document_id="00000000-0000-0000-0000-000000000001",
        matter_id="00000000-0000-0000-0000-000000000002",
        obligations=[{"id": "obl-1", "clause_text": "NDA", "topic": "confidentiality"}],
        gaps=[{"obligation_id": "obl-1", "severity": "partial", "gap_description": "x", "recommendation": "y", "law_reference": "GDPR", "clause_excerpt": "NDA"}],
        tool_calls=5,
        steps=["extract_obligations", "search_law", "compare_clause", "finalize_report"],
    )
    assert report["tool_calls_used"] == 5
    assert len(report["gaps"]) == 1
    assert "confidentiality" in report["summary"] or "1" in report["summary"]


def test_max_tool_calls_budget_constant():
    assert MAX_TOOL_CALLS == 12

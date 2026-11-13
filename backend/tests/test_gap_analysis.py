"""The gap report is the checklist review written for the interface, every step in the audit log (D-017)."""
import asyncio
import uuid
from types import SimpleNamespace

from services.agents import gap_analysis
from services.agents.contract_review import ItemResult, Review


def test_each_result_becomes_a_row_and_each_step_is_logged(monkeypatch):
    logged = []

    async def fake_log(_db, _user, action, _resource, resource_id=None, details=None):
        logged.append((action, details))

    async def fake_review(_db, _document_id, *, checklist, user_role, step):
        await step("search_contract", {"item": "governing_law"})
        await step("check_item", {"item": "governing_law", "status": "present", "calls": 1})
        return Review(
            items=[
                ItemResult("governing_law", "Governing Law", "present", quote="laws of New York", chunk_id="7", calls=1),
                ItemResult("audit_rights", "Audit Rights", "missing", calls=1),
                ItemResult("insurance", "Insurance", "not_verified", quote="insured", calls=2),
                ItemResult("data_processing_terms", "Data processing terms", "not_checked", error="model down",
                           law_reference="GDPR Art. 28", calls=2),
            ],
            calls=6, budget=22, seconds=3.0,
        )

    monkeypatch.setattr(gap_analysis, "log_audit", fake_log)
    monkeypatch.setattr(gap_analysis, "review_contract", fake_review)
    report = asyncio.run(
        gap_analysis.run_gap_analysis(None, matter_id=uuid.uuid4(), document_id=uuid.uuid4(), user=SimpleNamespace(role="owner"))
    )
    assert [g["severity"] for g in report["gaps"]] == ["aligned", "missing", "partial", "not checked"]
    assert report["gaps"][0]["chunk_id"] == "7" and report["gaps"][3]["law_reference"] == "GDPR Art. 28"
    assert report["tool_calls_used"] == 6 and report["call_budget"] == 22
    assert report["summary"].startswith("Checked 4 clause types: 1 found, 1 missing, 2 to check by hand")
    assert [action for action, _ in logged] == ["agent_step", "agent_step", "gap_analysis_complete"]

from services.playbook import run_playbook_checks
from services.clause_risk import score_document_risk


def test_playbook_nda_mutual():
    text = "This is a mutual non-disclosure agreement with disclosure required by law."
    results = run_playbook_checks(text, "nda")
    assert any(r["id"] == "nda-mutual" and r["passed"] for r in results)


def test_risk_scoring():
    text = "unlimited liability and indemnification apply."
    score = score_document_risk(text)
    assert score["risk_level"] == "high"

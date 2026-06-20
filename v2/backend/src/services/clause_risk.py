"""Heuristic clause risk scoring from playbook + keyword signals."""
from __future__ import annotations

from services.playbook import run_playbook_checks

HIGH_RISK = ("indemnif", "unlimited liability", "exclusive jurisdiction", "non-compete")
MEDIUM_RISK = ("termination for convenience", "audit rights", "assignment")


def score_document_risk(text: str, *, doc_type: str = "contract") -> dict:
    lower = text.lower()
    high = [k for k in HIGH_RISK if k in lower]
    medium = [k for k in MEDIUM_RISK if k in lower]
    playbook = run_playbook_checks(text, doc_type)
    failed = [p for p in playbook if not p["passed"]]

    if high or any(p["severity"] == "high" and not p["passed"] for p in playbook):
        level = "high"
    elif medium or failed:
        level = "medium"
    else:
        level = "low"

    return {
        "risk_level": level,
        "high_signals": high,
        "medium_signals": medium,
        "playbook": playbook,
    }

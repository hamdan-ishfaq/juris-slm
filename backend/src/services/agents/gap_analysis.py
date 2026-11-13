"""Gap analysis of one contract: the checklist review (D-017), written as a report and recorded in the audit log."""
from __future__ import annotations

import uuid

from sqlalchemy.ext.asyncio import AsyncSession

from db import User
from services.agents.contract_review import DEFAULT_CHECKLIST, ItemResult, review_contract
from services.audit_log import log_audit

# How each checklist result reads in the report, which the interface colours by severity.
_SEVERITY = {"present": "aligned", "missing": "missing", "not_verified": "partial", "not_checked": "not checked"}


def _gap(item: ItemResult) -> dict:
    if item.status == "present":
        description = f"Found: “{item.quote}”"
        recommendation = "Review the quoted clause."
    elif item.status == "missing":
        description = f"No {item.label.lower()} clause found in the contract."
        recommendation = f"Add a {item.label.lower()} clause, or record why the contract doesn't need one."
    elif item.status == "not_verified":
        description = f"The model reported a {item.label.lower()} clause, but its quote wasn't found in the text."
        recommendation = "Check this clause by hand."
    else:
        description = f"Not checked: {item.error or 'no answer'}."
        recommendation = "Run the analysis again, or check this clause by hand."
    return {
        "obligation_id": item.key,
        "clause_type": item.label,
        "clause_excerpt": item.quote[:300],
        "chunk_id": item.chunk_id,
        "law_reference": item.law_reference or "",
        "severity": _SEVERITY[item.status],
        "gap_description": description,
        "recommendation": recommendation,
        "model_calls": item.calls,
    }


async def run_gap_analysis(
    db: AsyncSession,
    *,
    matter_id: uuid.UUID,
    document_id: uuid.UUID,
    user: User,
    baseline: str = "gdpr",
) -> dict:
    steps: list[str] = []

    async def step(name: str, detail: dict) -> None:
        steps.append(name)
        await log_audit(
            db, user, "agent_step", "gap_analysis", resource_id=str(document_id),
            details={"step": name, "baseline": baseline, **detail},
        )

    review = await review_contract(db, document_id, checklist=DEFAULT_CHECKLIST, user_role=user.role, step=step)
    gaps = [_gap(item) for item in review.items]
    found = sum(item.status == "present" for item in review.items)
    missing = sum(item.status == "missing" for item in review.items)
    unsure = len(review.items) - found - missing
    summary = (
        f"Checked {len(review.items)} clause types: {found} found, {missing} missing"
        + (f", {unsure} to check by hand" if unsure else "")
        + f". {review.calls} model calls of a budget of {review.budget}."
    )
    await log_audit(
        db, user, "gap_analysis_complete", "gap_analysis", resource_id=str(document_id),
        details={"model_calls": review.calls, "missing": missing, "seconds": review.seconds},
    )
    return {
        "document_id": str(document_id),
        "matter_id": str(matter_id),
        "obligations": [{"id": g["obligation_id"], "topic": g["clause_type"], "clause_text": g["clause_excerpt"]} for g in gaps],
        "gaps": gaps,
        "summary": summary,
        "tool_calls_used": review.calls,
        "call_budget": review.budget,
        "steps_completed": steps,
        "seconds": review.seconds,
    }

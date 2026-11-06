"""Phase 9D — bounded regulatory gap analysis orchestrator."""
from __future__ import annotations

import uuid

from sqlalchemy.ext.asyncio import AsyncSession

from db import User
from services.agents.tools import compare_clause, extract_clauses, finalize_report, search_law
from services.audit_log import log_audit

MAX_TOOL_CALLS = 12


async def run_gap_analysis(
    db: AsyncSession,
    *,
    matter_id: uuid.UUID,
    document_id: uuid.UUID,
    user: User,
    baseline: str = "gdpr",
) -> dict:
    tool_calls = 0
    steps: list[str] = []

    async def _step(name: str, detail: dict | None = None) -> None:
        steps.append(name)
        await log_audit(
            db,
            user,
            "agent_step",
            "gap_analysis",
            resource_id=str(document_id),
            details={"step": name, "baseline": baseline, **(detail or {})},
        )

    if tool_calls >= MAX_TOOL_CALLS:
        raise RuntimeError("Tool call budget exceeded")
    await _step("extract_obligations")
    obligations = await extract_clauses(db, document_id=document_id, user=user)
    tool_calls += 1

    gaps: list[dict] = []
    for obl in obligations:
        if tool_calls >= MAX_TOOL_CALLS:
            break
        await _step("search_law", {"obligation_id": obl.get("id"), "topic": obl.get("topic")})
        law_hits = await search_law(db, topic=obl.get("topic", "general"), query_override=None, user=user)
        tool_calls += 1

        if tool_calls >= MAX_TOOL_CALLS:
            break
        await _step("compare_clause", {"obligation_id": obl.get("id")})
        gaps.append(compare_clause(obligation=obl, law_hits=law_hits))
        tool_calls += 1

    if tool_calls >= MAX_TOOL_CALLS:
        raise RuntimeError("Tool call budget exceeded before finalize")
    await _step("finalize_report", {"gap_count": len(gaps)})
    report = finalize_report(
        document_id=document_id,
        matter_id=matter_id,
        obligations=obligations,
        gaps=gaps,
        tool_calls=tool_calls + 1,
        steps=steps + ["finalize_report"],
    )
    tool_calls += 1

    await log_audit(
        db,
        user,
        "gap_analysis_complete",
        "gap_analysis",
        resource_id=str(document_id),
        details={"tool_calls": tool_calls, "gap_count": len(gaps)},
    )
    return report

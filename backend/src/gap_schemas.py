"""The gap analysis report: one row per checklist item (D-017)."""
from __future__ import annotations

from uuid import UUID

from pydantic import BaseModel, Field


class ObligationItem(BaseModel):
    id: str
    clause_text: str
    topic: str


class GapItem(BaseModel):
    obligation_id: str
    clause_type: str = ""
    clause_excerpt: str
    chunk_id: str | None = None  # the chunk the quote was found in
    law_reference: str
    severity: str
    gap_description: str
    recommendation: str
    model_calls: int = 0


class GapReport(BaseModel):
    document_id: UUID
    matter_id: UUID
    obligations: list[ObligationItem] = Field(default_factory=list)
    gaps: list[GapItem] = Field(default_factory=list)
    summary: str = ""
    tool_calls_used: int = 0
    call_budget: int = 0
    steps_completed: list[str] = Field(default_factory=list)
    seconds: float = 0.0


class GapAnalysisRequest(BaseModel):
    document_id: UUID
    baseline: str = Field(default="gdpr", description="Regulatory baseline: gdpr, bgb")


class GapAnalysisJobResponse(BaseModel):
    job_id: str
    status: str


class GapAnalysisStatusResponse(BaseModel):
    job_id: str
    status: str
    progress_step: str | None = None
    report: GapReport | None = None
    error: str | None = None

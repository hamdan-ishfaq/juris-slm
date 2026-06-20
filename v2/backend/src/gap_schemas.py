"""Phase 9D — regulatory gap analysis report schema."""
from __future__ import annotations

from enum import Enum
from uuid import UUID

from pydantic import BaseModel, Field


class GapSeverity(str, Enum):
    aligned = "aligned"
    partial = "partial"
    missing = "missing"
    high = "high"
    medium = "medium"
    low = "low"


class ObligationItem(BaseModel):
    id: str
    clause_text: str
    topic: str


class GapItem(BaseModel):
    obligation_id: str
    clause_excerpt: str
    law_reference: str
    severity: str
    gap_description: str
    recommendation: str
    law_excerpt: str | None = None


class GapReport(BaseModel):
    document_id: UUID
    matter_id: UUID
    obligations: list[ObligationItem] = Field(default_factory=list)
    gaps: list[GapItem] = Field(default_factory=list)
    summary: str = ""
    tool_calls_used: int = 0
    steps_completed: list[str] = Field(default_factory=list)


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

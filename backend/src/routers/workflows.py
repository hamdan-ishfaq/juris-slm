"""Phase 9D — bounded agent workflow endpoints."""
from __future__ import annotations

import uuid
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy.ext.asyncio import AsyncSession

from db import User, get_db
from deps import get_current_user, require_matter_access
from rate_limit import limiter, rate_limit_exempt
from gap_schemas import (
    GapAnalysisJobResponse,
    GapAnalysisRequest,
    GapAnalysisStatusResponse,
    GapReport,
)
from services.workflow_jobs import create_job, get_job

router = APIRouter(prefix="/api/v1", tags=["workflows"])


@router.post("/matters/{matter_id}/workflows/gap-analysis", response_model=GapAnalysisJobResponse)
@limiter.limit("5/hour", exempt_when=rate_limit_exempt)
async def start_gap_analysis(
    request: Request,
    matter_id: UUID,
    body: GapAnalysisRequest,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    await require_matter_access(matter_id, user, db, min_role="viewer")
    job_id = create_job(
        "gap_analysis",
        meta={
            "matter_id": str(matter_id),
            "document_id": str(body.document_id),
            "user_id": str(user.id),
            "baseline": body.baseline,
        },
    )
    try:
        from worker import gap_analysis_task

        gap_analysis_task.delay(job_id)
    except Exception as exc:
        raise HTTPException(status_code=503, detail=f"Could not queue gap analysis: {exc}") from exc
    return GapAnalysisJobResponse(job_id=job_id, status="queued")


@router.get("/workflows/gap-analysis/{job_id}", response_model=GapAnalysisStatusResponse)
async def gap_analysis_status(
    job_id: str,
    user: User = Depends(get_current_user),
):
    job = get_job(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    meta = job.get("meta") or {}
    if meta.get("user_id") and meta.get("user_id") != str(user.id):
        raise HTTPException(status_code=404, detail="Job not found")
    report = job.get("report")
    gap_report = GapReport(**report) if report else None
    return GapAnalysisStatusResponse(
        job_id=job_id,
        status=job.get("status", "unknown"),
        progress_step=job.get("progress_step"),
        report=gap_report,
        error=job.get("error"),
    )

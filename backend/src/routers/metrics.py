"""Prometheus metrics."""
from __future__ import annotations

import hmac

from fastapi import APIRouter, HTTPException, Request, Response
from prometheus_client import CONTENT_TYPE_LATEST, generate_latest

from config import settings
from services.metrics import REGISTRY

router = APIRouter(tags=["metrics"])


def _allowed(request: Request) -> bool:
    """Open in development. In production, only with METRICS_TOKEN as a bearer token, so usage isn't visible to anyone."""
    if not settings.is_production:
        return True
    expected = settings.metrics_token
    supplied = request.headers.get("authorization", "").removeprefix("Bearer ").strip()
    return bool(expected) and hmac.compare_digest(supplied.encode(), expected.encode())


@router.get("/metrics")
async def metrics(request: Request):
    if not _allowed(request):
        raise HTTPException(status_code=404, detail="Not Found")
    return Response(generate_latest(REGISTRY), media_type=CONTENT_TYPE_LATEST)

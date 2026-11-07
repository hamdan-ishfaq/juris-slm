"""Prometheus metrics — Phase 10 ops."""
from __future__ import annotations

from fastapi import APIRouter, Response

router = APIRouter(tags=["metrics"])

try:
    from prometheus_client import CONTENT_TYPE_LATEST, CollectorRegistry, Counter, generate_latest

    _REGISTRY = CollectorRegistry()
    HTTP_REQUESTS = Counter(
        "juris_http_requests_total",
        "Total HTTP requests served",
        ["method", "endpoint"],
        registry=_REGISTRY,
    )
    _PROMETHEUS_OK = True
except ImportError:
    _PROMETHEUS_OK = False


@router.get("/metrics")
async def metrics():
    if not _PROMETHEUS_OK:
        body = "# HELP juris_up JurisGuard API is running\njuris_up 1\n"
        return Response(body, media_type="text/plain; version=0.0.4")
    return Response(generate_latest(_REGISTRY), media_type=CONTENT_TYPE_LATEST)

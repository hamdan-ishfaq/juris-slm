"""Optional Langfuse / structured RAG tracing."""
from __future__ import annotations

import logging
import time
from contextlib import contextmanager
from contextvars import ContextVar
from typing import Any, Iterator

from config import settings
from services.metrics import RAG_STAGE_SECONDS

logger = logging.getLogger("jurisguard.trace")

_stage_times: ContextVar[dict[str, float] | None] = ContextVar("stage_times", default=None)


@contextmanager
def collect_stage_times() -> Iterator[dict[str, float]]:
    """Gather the milliseconds spent in each stage during one request."""
    times: dict[str, float] = {}
    token = _stage_times.set(times)
    try:
        yield times
    finally:
        _stage_times.reset(token)


@contextmanager
def trace_rag_step(name: str, **metadata: Any) -> Iterator[None]:
    start = time.perf_counter()
    try:
        yield
    finally:
        elapsed = time.perf_counter() - start
        RAG_STAGE_SECONDS.labels(stage=name).observe(elapsed)
        times = _stage_times.get()
        if times is not None:
            times[name] = times.get(name, 0.0) + elapsed * 1000
        if settings.tracing_enabled:
            payload = {"step": name, "latency_ms": round(elapsed * 1000, 2), **metadata}
            logger.info("rag_trace %s", payload)
            _langfuse_event(name, payload)


def _langfuse_event(name: str, metadata: dict) -> None:
    if not settings.langfuse_public_key or not settings.langfuse_secret_key:
        return
    try:
        import httpx

        url = f"{settings.langfuse_host.rstrip('/')}/api/public/ingestion"
        httpx.post(
            url,
            json={
                "batch": [
                    {
                        "type": "trace-create",
                        "body": {"name": name, "metadata": metadata},
                    }
                ]
            },
            headers={
                "Authorization": f"Basic {settings.langfuse_public_key}:{settings.langfuse_secret_key}",
            },
            timeout=5.0,
        )
    except Exception:
        pass

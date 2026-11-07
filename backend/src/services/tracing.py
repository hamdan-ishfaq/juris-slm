"""Optional Langfuse / structured RAG tracing."""
from __future__ import annotations

import logging
import time
from contextlib import contextmanager
from typing import Any, Iterator

from config import settings

logger = logging.getLogger("jurisguard.trace")


@contextmanager
def trace_rag_step(name: str, **metadata: Any) -> Iterator[None]:
    if not settings.tracing_enabled:
        yield
        return
    start = time.perf_counter()
    try:
        yield
    finally:
        elapsed_ms = (time.perf_counter() - start) * 1000
        payload = {"step": name, "latency_ms": round(elapsed_ms, 2), **metadata}
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

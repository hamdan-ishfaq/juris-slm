"""LLM call audit logging — task, model, latency (no budget caps)."""
from __future__ import annotations

import logging
import time
from contextlib import asynccontextmanager
from typing import AsyncIterator

logger = logging.getLogger("jurisguard.llm")


@asynccontextmanager
async def llm_call_span(*, task: str, model: str, tier: str) -> AsyncIterator[None]:
    start = time.perf_counter()
    try:
        yield
    finally:
        elapsed_ms = (time.perf_counter() - start) * 1000
        logger.info(
            "llm_call task=%s tier=%s model=%s latency_ms=%.1f",
            task,
            tier,
            model,
            elapsed_ms,
        )

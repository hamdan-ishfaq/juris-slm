"""Prometheus metrics served at /metrics."""
from __future__ import annotations

from prometheus_client import CollectorRegistry, Histogram

REGISTRY = CollectorRegistry()
# Seconds, from a cache hit to a cold model load.
_BUCKETS = (0.01, 0.05, 0.1, 0.25, 0.5, 1, 2, 5, 10, 20, 30, 60, 120)

RAG_STAGE_SECONDS = Histogram(
    "juris_rag_stage_seconds",
    "Time spent in each stage of answering a question",
    ["stage"],
    buckets=_BUCKETS,
    registry=REGISTRY,
)
FIRST_TOKEN_SECONDS = Histogram(
    "juris_first_token_seconds",
    "Time from a streamed question to its first answer token",
    buckets=_BUCKETS,
    registry=REGISTRY,
)

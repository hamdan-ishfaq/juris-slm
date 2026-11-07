"""Stage timing for answering a question: Prometheus histograms, per-request times, and OpenTelemetry spans.

Spans are exported only when OTEL_EXPORTER_OTLP_ENDPOINT points at a collector, such as a local Jaeger, so nothing leaves
the machine by default. Spans carry sizes and identifiers, never the question or answer text. See docs/DECISIONS.md, D-008.
"""
from __future__ import annotations

import logging
import os
import time
from contextlib import contextmanager
from contextvars import ContextVar
from typing import Any, Iterator

from opentelemetry import trace

from config import settings
from services.metrics import RAG_STAGE_SECONDS

logger = logging.getLogger("jurisguard.trace")

_stage_times: ContextVar[dict[str, float] | None] = ContextVar("stage_times", default=None)


def _exporter_endpoint() -> str | None:
    return os.environ.get("OTEL_EXPORTER_OTLP_TRACES_ENDPOINT") or os.environ.get("OTEL_EXPORTER_OTLP_ENDPOINT")


def _make_tracer() -> trace.Tracer:
    if not _exporter_endpoint():
        return trace.NoOpTracer()
    from opentelemetry.exporter.otlp.proto.http.trace_exporter import OTLPSpanExporter
    from opentelemetry.sdk.resources import Resource
    from opentelemetry.sdk.trace import TracerProvider
    from opentelemetry.sdk.trace.export import BatchSpanProcessor

    provider = TracerProvider(resource=Resource.create({"service.name": "jurisguard-api"}))
    provider.add_span_processor(BatchSpanProcessor(OTLPSpanExporter()))
    return provider.get_tracer("jurisguard")


_tracer = _make_tracer()


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
def trace_rag_step(name: str, **attributes: Any) -> Iterator[trace.Span]:
    """Time one stage. Pass only sizes and identifiers as attributes, never user text."""
    start = time.perf_counter()
    with _tracer.start_as_current_span(name, attributes=attributes) as span:
        try:
            yield span
        finally:
            elapsed = time.perf_counter() - start
            RAG_STAGE_SECONDS.labels(stage=name).observe(elapsed)
            times = _stage_times.get()
            if times is not None:
                times[name] = times.get(name, 0.0) + elapsed * 1000
            if settings.tracing_enabled:
                logger.info("rag_trace %s", {"step": name, "latency_ms": round(elapsed * 1000, 2), **attributes})

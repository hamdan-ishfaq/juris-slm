"""Every stage of answering is timed, into Prometheus and into the response."""
import asyncio

from services import rag
from services.metrics import REGISTRY
from services.tracing import collect_stage_times, trace_rag_step


def _count(stage):
    return REGISTRY.get_sample_value("juris_rag_stage_seconds_count", {"stage": stage}) or 0


def test_a_timed_stage_reaches_prometheus_even_with_tracing_off(monkeypatch):
    monkeypatch.setattr("services.tracing.settings.tracing_enabled", False)
    before = _count("unit_test_stage")
    with trace_rag_step("unit_test_stage"):
        pass
    assert _count("unit_test_stage") == before + 1


def test_stage_times_are_collected_per_request():
    with collect_stage_times() as times:
        with trace_rag_step("embed"):
            pass
        with trace_rag_step("embed"):
            pass
    assert set(times) == {"embed"}
    assert times["embed"] >= 0


def test_stages_outside_a_request_are_not_collected():
    with trace_rag_step("orphan"):
        pass
    with collect_stage_times() as times:
        pass
    assert times == {}


def test_answer_reports_its_stage_times(monkeypatch):
    async def fake_answer(*_args, **_kwargs):
        with trace_rag_step("generate"):
            pass
        return {"answer": "a", "sources": [], "answer_mode": "llm"}

    monkeypatch.setattr(rag, "_answer_question", fake_answer)
    result = asyncio.run(rag.answer_question(None, "What does Article 6 say?"))
    assert {"generate", "total"} <= set(result["timings_ms"])


def test_metrics_endpoint_exposes_stage_histograms():
    from fastapi.testclient import TestClient

    from routers.metrics import router
    from fastapi import FastAPI

    app = FastAPI()
    app.include_router(router)
    with trace_rag_step("unit_test_stage"):
        pass
    body = TestClient(app).get("/metrics").text
    assert "juris_rag_stage_seconds_bucket" in body
    assert "juris_first_token_seconds" in body


def test_grounding_embeds_only_the_answer(monkeypatch):
    import numpy as np

    embedded = []

    def fake_embed(texts):
        embedded.append(list(texts))
        return [np.ones(4, dtype=np.float32)]

    monkeypatch.setattr(rag, "embed_texts", fake_embed)
    monkeypatch.setattr(rag.settings, "semantic_context_min_cosine", 0.5)
    stored = [np.ones(4, dtype=np.float32), np.zeros(4, dtype=np.float32) + 0.1]
    assert rag._answer_uses_context("The controller must notify.", "context", chunk_vectors=stored)
    assert embedded == [["The controller must notify."]]


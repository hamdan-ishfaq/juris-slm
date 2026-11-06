"""answer_mode must say whether the LLM answered, the fallback copied text, or the system refused."""
import asyncio

import pytest

from services import rag

CHUNK = {
    "id": 1,
    "content": "Processing is lawful only if the data subject has given consent to the processing.",
    "metadata": {"title": "GDPR", "source": "gdpr"},
    "rerank_score": 5.0,
}
GROUNDED = (
    "Under GDPR Article 6, processing is lawful only if the data subject has given consent "
    "to the processing of personal data."
)
QUESTION = "When is processing of personal data lawful under GDPR Article 6?"


@pytest.fixture
def pipeline(monkeypatch):
    calls = {"cache_reads": 0}

    async def fake_retrieve(*_args, **_kwargs):
        return calls["ranked"]

    async def fake_generate(*_args, **_kwargs):
        return calls["answer"]

    async def fake_dlg(*_args, **_kwargs):
        return ""

    def fake_cache_read(*_args, **_kwargs):
        calls["cache_reads"] += 1
        return calls.get("cached")

    monkeypatch.setattr(rag, "_retrieve_and_rank", fake_retrieve)
    monkeypatch.setattr(rag, "generate_rag", fake_generate)
    monkeypatch.setattr(rag, "get_cached_answer", fake_cache_read)
    monkeypatch.setattr(rag, "set_cached_answer", lambda *a, **k: None)
    monkeypatch.setattr("services.dlg.fetch_dlg_context", fake_dlg)
    calls.update(ranked=[CHUNK], answer=GROUNDED)
    return calls


def _ask(**kwargs):
    return asyncio.run(rag.answer_question(None, QUESTION, **kwargs))


def test_grounded_answer_is_llm(pipeline):
    assert _ask()["answer_mode"] == rag.ANSWER_LLM


def test_model_refusal_is_recorded_as_extractive(pipeline):
    pipeline["answer"] = "As an AI, I cannot assist with that."
    assert _ask()["answer_mode"] == rag.ANSWER_EXTRACTIVE


def test_no_retrieval_is_refused(pipeline):
    pipeline["ranked"] = []
    result = _ask()
    assert result["answer_mode"] == rag.ANSWER_REFUSED
    assert result["sources"] == []


def test_short_query_is_refused(pipeline):
    result = asyncio.run(rag.answer_question(None, "GDPR?"))
    assert result["answer_mode"] == rag.ANSWER_REFUSED


def test_skip_cache_does_not_read_the_cache(pipeline):
    pipeline["cached"] = {"answer": "stale", "model": "m", "sources": []}
    assert _ask(skip_cache=True)["answer"] != "stale"
    assert pipeline["cache_reads"] == 0
    assert _ask()["answer"] == "stale"

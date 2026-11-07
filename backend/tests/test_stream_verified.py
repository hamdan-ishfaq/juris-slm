"""Streaming sends a draft, then the checked answer, using the same pipeline as a normal request."""
import asyncio

from services import rag

CHUNK = {
    "id": 1,
    "content": "Article 6. Processing is lawful only if the data subject has given consent to the processing.",
    "metadata": {"title": "GDPR", "source": "gdpr"},
    "rerank_score": 5.0,
}


def _setup(monkeypatch, tokens):
    async def fake_retrieve(*_args, **_kwargs):
        return [CHUNK]

    async def fake_stream(*_args, **_kwargs):
        for token in tokens:
            yield token

    async def no_vectors(*_args, **_kwargs):
        return []

    async def no_dlg(*_args, **_kwargs):
        return ""

    stored = []
    monkeypatch.setattr(rag, "_retrieve_and_rank", fake_retrieve)
    monkeypatch.setattr("services.llm_client.generate_rag_stream", fake_stream)
    monkeypatch.setattr(rag, "_stored_vectors", no_vectors)
    monkeypatch.setattr(rag, "get_cached_answer", lambda *a, **k: None)
    monkeypatch.setattr(rag, "set_cached_answer", lambda *a, **k: stored.append(k["payload"]))
    monkeypatch.setattr("services.dlg.fetch_dlg_context", no_dlg)
    return stored


def _events(question="Under GDPR Article 6, when is processing lawful?"):
    async def collect():
        return [event async for event in rag.answer_question_stream(None, question)]

    return asyncio.run(collect())


def test_a_citation_note_counts_as_a_replacement(monkeypatch):
    _setup(monkeypatch, ["Under GDPR Article 99, processing is lawful only if the data subject has given consent to the processing."])
    final = _events()[-1]
    assert final["replaced"] is True
    assert "could not be verified" in final["answer"]


def test_draft_tokens_then_a_final_checked_answer(monkeypatch):
    grounded = ["Under GDPR Article 6, processing is lawful only if the data subject ", "has given consent to the processing."]
    _setup(monkeypatch, grounded)
    events = _events()
    assert [e["type"] for e in events if e["type"] == "token"] == ["token", "token"]
    final = events[-1]
    assert final["type"] == "final"
    assert final["answer_mode"] == "llm"
    assert final["replaced"] is False
    assert final["sources"]


def test_an_ungrounded_draft_is_replaced_by_the_checked_answer(monkeypatch):
    stored = _setup(monkeypatch, ["The weather in Paris is pleasant in spring and autumn."])
    final = _events()[-1]
    assert final["type"] == "final"
    assert final["answer_mode"] == "extractive"
    assert final["replaced"] is True
    assert "weather" not in final["answer"]
    assert stored and stored[0]["answer"] == final["answer"]


def test_a_refusal_comes_as_a_final_answer_without_tokens(monkeypatch):
    _setup(monkeypatch, ["unused"])

    async def weak_retrieve(*_args, **_kwargs):
        return [{**CHUNK, "rerank_score": -9.0}]

    monkeypatch.setattr(rag, "_retrieve_and_rank", weak_retrieve)
    events = _events("What is the capital of France?")
    assert [e["type"] for e in events] == ["final"]
    assert events[0]["answer_mode"] == "refused"


def test_stream_reports_stage_times(monkeypatch):
    _setup(monkeypatch, ["Under GDPR Article 6, processing is lawful only if the data subject has given consent."])
    final = _events()[-1]
    assert {"retrieve", "generate", "total"} <= set(final["timings_ms"])


async def _no_graph(*_args, **_kwargs):
    return ""


def test_a_question_about_a_chosen_document_is_not_refused_on_retrieval_score(monkeypatch):
    _setup(monkeypatch, ["Under GDPR Article 6, processing is lawful only if the data subject has given consent to the processing."])

    async def weak_retrieve(*_args, **_kwargs):
        return [{**CHUNK, "rerank_score": -9.0}]

    monkeypatch.setattr(rag, "_retrieve_and_rank", weak_retrieve)
    monkeypatch.setattr("services.vector_store.fetch_graph_context", _no_graph)
    document = "00000000-0000-0000-0000-000000000001"

    async def collect():
        return [e async for e in rag.answer_question_stream(None, "Under GDPR Article 6, when is processing lawful?", document_id=document)]

    final = asyncio.run(collect())[-1]
    assert final["answer_mode"] != "refused"


def test_a_short_correct_answer_is_kept(monkeypatch):
    """A one-line factual answer shares few words with the chunk, and used to be replaced by quoted text."""
    import numpy as np

    _setup(monkeypatch, ["Consent is the lawful basis under Article 6."])

    async def stored_vectors(*_args, **_kwargs):
        return [np.ones(4, dtype=np.float32)]

    monkeypatch.setattr(rag, "_stored_vectors", stored_vectors)
    monkeypatch.setattr(rag, "embed_texts", lambda texts: [np.ones(4, dtype=np.float32)])
    final = _events()[-1]
    assert final["answer_mode"] == "llm"

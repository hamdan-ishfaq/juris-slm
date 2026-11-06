"""The context cap, org scoping in multi-query search, and session use in compare."""
import asyncio
import uuid

from services import rag
from services.rag import _format_context


def _hit(content, parent=None, hit_id=1):
    metadata = {"title": "Doc"}
    if parent:
        metadata["parent_content"] = parent
    return {"id": hit_id, "content": content, "metadata": metadata}


def test_total_context_stays_within_the_cap(monkeypatch):
    monkeypatch.setattr(rag.settings, "rag_max_context_chars", 6000)
    hits = [_hit("x" * 2500, hit_id=i) for i in range(5)]
    context, sources = _format_context(hits)
    assert len(context) <= 6000
    assert len(sources) == 2


def test_oversized_section_falls_back_to_the_matched_chunk(monkeypatch):
    monkeypatch.setattr(rag.settings, "rag_max_context_chars", 6000)
    context, sources = _format_context([_hit("the matched clause", parent="y" * 10000)])
    assert "the matched clause" in context
    assert sources[0]["content"] == "the matched clause"


def test_oversized_first_chunk_is_cut_rather_than_dropped(monkeypatch):
    monkeypatch.setattr(rag.settings, "rag_max_context_chars", 6000)
    context, sources = _format_context([_hit("z" * 10000)])
    assert 0 < len(context) <= 6000
    assert len(sources) == 1


def test_a_later_section_that_fits_only_as_a_chunk_still_counts(monkeypatch):
    monkeypatch.setattr(rag.settings, "rag_max_context_chars", 6000)
    hits = [_hit("a" * 5000, hit_id=1), _hit("short clause", parent="b" * 5000, hit_id=2)]
    context, sources = _format_context(hits)
    assert "short clause" in context
    assert len(sources) == 2


def test_multi_query_search_keeps_the_org(monkeypatch):
    org = uuid.uuid4()
    seen = []

    async def fake_embed(_question, *, use_hyde):
        return None, None

    async def fake_retrieve(_db, _question, _vector, **kwargs):
        seen.append(kwargs["org_id"])
        return [{"id": 1, "content": "c"}]

    monkeypatch.setattr(rag, "_embed_query", fake_embed)
    monkeypatch.setattr(rag, "_retrieve", fake_retrieve)
    asyncio.run(
        rag._retrieve_multi_query(
            None,
            ["first", "second"],
            accessible_ids=None,
            include_law=True,
            user_role="member",
            doc_uuid=None,
            org_id=org,
        )
    )
    assert seen == [org, org]


def test_compare_never_uses_the_session_concurrently(monkeypatch):
    active = 0
    peak = 0

    async def fake_answer(*_args, **_kwargs):
        nonlocal active, peak
        active += 1
        peak = max(peak, active)
        await asyncio.sleep(0)
        active -= 1
        return {"answer": "a", "sources": []}

    monkeypatch.setattr(rag, "answer_question", fake_answer)
    monkeypatch.setattr(rag, "_guard_query", lambda _question: None)
    asyncio.run(rag.answer_compare(None, "compare this", document_id="d", user=None))
    assert peak == 1


class _FakeModel:
    def predict(self, pairs):
        return [float(content.split()[-1]) for _question, content in pairs]


def _retrieve_and_rank(monkeypatch, question, contents, *, include_law=False):
    async def fake_embed(_question, *, use_hyde):
        return None, None

    async def fake_retrieve(*_args, **_kwargs):
        return [{"id": i, "content": content, "metadata": {}} for i, content in enumerate(contents)]

    monkeypatch.setattr(rag, "_embed_query", fake_embed)
    monkeypatch.setattr(rag, "_retrieve", fake_retrieve)
    monkeypatch.setattr("services.reranker.get_reranker", lambda: _FakeModel())
    monkeypatch.setattr(rag.settings, "rag_rerank_k", 2)
    monkeypatch.setattr(rag.settings, "crag_retry_enabled", False)
    return asyncio.run(
        rag._retrieve_and_rank(
            None,
            question,
            accessible_ids=None,
            include_law=include_law,
            user_role="member",
            doc_uuid=None,
            use_hyde=False,
        )
    )


def test_law_search_is_reordered_without_a_citation(monkeypatch):
    ranked = _retrieve_and_rank(monkeypatch, "How may employee data be used?", ["a 1", "b 2", "c 9"], include_law=True)
    assert [hit["content"] for hit in ranked] == ["c 9", "b 2"]


def test_question_citing_a_provision_is_reordered(monkeypatch):
    ranked = _retrieve_and_rank(monkeypatch, "What does Article 6 say?", ["a 1", "b 2", "c 9"])
    assert [hit["content"] for hit in ranked] == ["c 9", "b 2"]


def test_document_question_without_a_citation_keeps_retrieval_order_and_gets_scores(monkeypatch):
    ranked = _retrieve_and_rank(monkeypatch, "What is the cap on liability?", ["a 1", "b 2", "c 9"])
    assert [hit["content"] for hit in ranked] == ["a 1", "b 2"]
    assert [hit["rerank_score"] for hit in ranked] == [1.0, 2.0]


def test_confidence_gate_uses_the_best_score_not_the_first(monkeypatch):
    monkeypatch.setattr(rag.settings, "rag_min_rerank_score", -2.0)
    assert rag._apply_confidence_gate([{"rerank_score": -5.0}, {"rerank_score": 1.0}])
    assert not rag._apply_confidence_gate([{"rerank_score": -5.0}, {"rerank_score": -3.0}])

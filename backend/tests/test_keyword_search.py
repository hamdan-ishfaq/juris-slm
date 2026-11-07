"""Keyword search must match any term, and only join the merge when a question cites a provision."""
import asyncio

import pytest

from services import vector_store
from services.vector_store import _or_tsquery, has_legal_reference


@pytest.mark.parametrize(
    "question",
    ["What does Article 6 say?", "See art. 6", "Art 6 GDPR", "Artikel 6 DSGVO", "under Section 26", "§ 26 BDSG", "§§ 433"],
)
def test_detects_citations(question):
    assert has_legal_reference(question)


@pytest.mark.parametrize(
    "question",
    ["What is the cap on liability?", "Does the party retain data?", "the 6 smart contracts", "partial 2 cases"],
)
def test_ignores_questions_without_citations(question):
    assert not has_legal_reference(question)


def test_or_query_keeps_terms_and_article_numbers_and_drops_stopwords():
    assert _or_tsquery("What is lawful processing under Article 6?") == "'lawful' | 'processing' | 'article' | '6'"


def test_or_query_is_empty_for_stopwords_only():
    assert _or_tsquery("what is the") == ""


def _hybrid(monkeypatch, question):
    vector_hit = {"id": 1, "content": "vector"}
    keyword_hit = {"id": 2, "content": "keyword"}
    calls = []

    async def fake_similar(*_args, **_kwargs):
        return [vector_hit]

    async def fake_fts(*_args, **_kwargs):
        calls.append(1)
        return [keyword_hit]

    monkeypatch.setattr(vector_store, "search_similar", fake_similar)
    monkeypatch.setattr(vector_store, "search_fts", fake_fts)
    monkeypatch.setattr(vector_store.settings, "hybrid_search_enabled", True)
    hits = asyncio.run(vector_store.hybrid_search(None, question, None, top_k=5))
    return {hit["id"] for hit in hits}, calls


def test_hybrid_merges_keyword_results_when_a_provision_is_cited(monkeypatch):
    ids, calls = _hybrid(monkeypatch, "What does Article 6 say?")
    assert ids == {1, 2}
    assert calls


def test_hybrid_is_vector_only_without_a_citation(monkeypatch):
    ids, calls = _hybrid(monkeypatch, "What is the cap on liability?")
    assert ids == {1}
    assert not calls

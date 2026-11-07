"""Unit tests for Phase 2 RRF merge."""
from __future__ import annotations

from services.rrf import rrf_merge


def test_rrf_merge_prefers_items_in_both_lists():
    vec = [{"id": 1, "content": "a"}, {"id": 2, "content": "b"}]
    fts = [{"id": 2, "content": "b"}, {"id": 3, "content": "c"}]
    merged = rrf_merge([vec, fts], k=60, top_k=3)
    ids = [h["id"] for h in merged]
    assert ids[0] == 2
    assert set(ids) == {1, 2, 3}


def test_rrf_merge_single_list():
    hits = [{"id": i, "content": str(i)} for i in range(5)]
    merged = rrf_merge([hits], top_k=3)
    assert len(merged) == 3
    assert merged[0]["id"] == 0

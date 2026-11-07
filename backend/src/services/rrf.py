"""Reciprocal Rank Fusion for merging multiple retrieval result lists."""
from __future__ import annotations

from typing import Any


def rrf_merge(lists: list[list[dict[str, Any]]], *, k: int = 60, top_k: int = 20) -> list[dict[str, Any]]:
    """Merge ranked hit lists using RRF. Each hit must have an ``id`` key."""
    scores: dict[Any, float] = {}
    by_id: dict[Any, dict[str, Any]] = {}

    for ranked in lists:
        for rank, hit in enumerate(ranked, start=1):
            hit_id = hit.get("id")
            if hit_id is None:
                continue
            scores[hit_id] = scores.get(hit_id, 0.0) + 1.0 / (k + rank)
            if hit_id not in by_id:
                by_id[hit_id] = dict(hit)

    ordered = sorted(scores.keys(), key=lambda hid: scores[hid], reverse=True)
    out: list[dict[str, Any]] = []
    for hid in ordered[:top_k]:
        hit = by_id[hid]
        hit["rrf_score"] = scores[hid]
        out.append(hit)
    return out

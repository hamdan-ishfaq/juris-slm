"""Redis-backed cache for law corpus Q&A responses."""
from __future__ import annotations

import hashlib
import json

from config import settings

_CACHE_STATS = {"hits": 0, "misses": 0}


def cache_metrics() -> dict:
    hits = _CACHE_STATS["hits"]
    misses = _CACHE_STATS["misses"]
    total = hits + misses
    return {
        "hits": hits,
        "misses": misses,
        "hit_rate": round(hits / total, 4) if total else 0.0,
        "enabled": settings.query_cache_enabled,
    }


def _cache_key(question: str, *, use_law_corpus: bool, document_id: str | None) -> str:
    norm = " ".join(question.lower().split())
    doc = document_id or ""
    raw = f"{norm}|law={use_law_corpus}|doc={doc}"
    return f"juris:qa:{hashlib.sha256(raw.encode()).hexdigest()}"


def get_cached_answer(question: str, *, use_law_corpus: bool, document_id: str | None) -> dict | None:
    if not settings.query_cache_enabled or not use_law_corpus or document_id:
        return None
    try:
        import redis

        client = redis.from_url(settings.redis_url, decode_responses=True)
        raw = client.get(_cache_key(question, use_law_corpus=use_law_corpus, document_id=document_id))
        if raw:
            _CACHE_STATS["hits"] += 1
            return json.loads(raw)
        _CACHE_STATS["misses"] += 1
    except Exception:
        return None
    return None


def set_cached_answer(
    question: str,
    *,
    use_law_corpus: bool,
    document_id: str | None,
    payload: dict,
) -> None:
    if not settings.query_cache_enabled or not use_law_corpus or document_id:
        return
    try:
        import redis

        client = redis.from_url(settings.redis_url, decode_responses=True)
        client.setex(
            _cache_key(question, use_law_corpus=use_law_corpus, document_id=document_id),
            settings.query_cache_ttl_seconds,
            json.dumps(payload),
        )
    except Exception:
        pass

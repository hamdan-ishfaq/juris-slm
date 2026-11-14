"""Redis-backed cache for law corpus Q&A responses."""
from __future__ import annotations

import hashlib
import json
import logging

from config import settings

logger = logging.getLogger(__name__)

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


# Bumped whenever the law corpus changes, and part of every key, so answers from before a re-ingest are never served.
CORPUS_VERSION_KEY = "juris:corpus_version"


def _client():
    import redis

    return redis.from_url(settings.redis_url, decode_responses=True)


def _cache_key(client, question: str, *, use_law_corpus: bool, document_id: str | None) -> str:
    norm = " ".join(question.lower().split())
    doc = document_id or ""
    version = client.get(CORPUS_VERSION_KEY) or "0"
    raw = f"{norm}|law={use_law_corpus}|doc={doc}|corpus={version}"
    return f"juris:qa:{hashlib.sha256(raw.encode()).hexdigest()}"


def bump_corpus_version() -> None:
    """Make every cached answer unreachable; called when a law corpus source finishes ingesting."""
    try:
        _client().incr(CORPUS_VERSION_KEY)
    except Exception:
        logger.warning("Could not bump the corpus version; cached answers may be stale for up to the TTL", exc_info=True)


def get_cached_answer(question: str, *, use_law_corpus: bool, document_id: str | None) -> dict | None:
    if not settings.query_cache_enabled or not use_law_corpus or document_id:
        return None
    try:
        client = _client()
        raw = client.get(_cache_key(client, question, use_law_corpus=use_law_corpus, document_id=document_id))
        if raw:
            _CACHE_STATS["hits"] += 1
            return json.loads(raw)
        _CACHE_STATS["misses"] += 1
    except Exception:
        logger.warning("Query cache read failed", exc_info=True)
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
        client = _client()
        client.setex(
            _cache_key(client, question, use_law_corpus=use_law_corpus, document_id=document_id),
            settings.query_cache_ttl_seconds,
            json.dumps(payload),
        )
    except Exception:
        logger.warning("Query cache write failed", exc_info=True)

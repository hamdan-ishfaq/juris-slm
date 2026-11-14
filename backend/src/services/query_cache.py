"""Redis-backed cache for law corpus Q&A responses, exact and semantic (D-022).

Keys include the corpus version, so a re-ingest makes older answers unreachable, and the organisation, because law
answers can draw on regulations one organisation uploaded. A semantic hit needs a bge-m3 cosine similarity of at least
``semantic_cache_threshold`` and the same cited provisions (article, paragraph, point) and laws as the cached question:
on 103 held-out near misses this served no wrong answer and answered 27 of 45 rewordings
(eval/reports/capacity_2026-11/). Similarity alone served 4 wrong answers on the first pair set.
"""
from __future__ import annotations

import base64
import hashlib
import json
import logging
import re

import numpy as np

from config import settings

logger = logging.getLogger(__name__)

_CACHE_STATS = {"hits": 0, "misses": 0, "semantic_hits": 0}


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


_LAWS = {"gdpr": r"\b(gdpr|dsgvo)\b", "bdsg": r"\bbdsg\b", "bgb": r"\bbgb\b", "ai_act": r"\bai act\b"}
_PROVISION = re.compile(r"(?:art(?:icle)?s?\.?|§|section)\s*(\d+)((?:\(\d+\))?(?:\([a-z]\))?)(?:\s*-\s*(\d+))?", re.I)


def cache_signature(question: str) -> list:
    """Provisions with paragraph and point, and the laws named; two questions must match exactly to share an answer."""
    q = question.lower()
    provisions = sorted(f"{m.group(1)}{m.group(2)}" + (f"-{m.group(3)}" if m.group(3) else "") for m in _PROVISION.finditer(q))
    laws = sorted(name for name, pattern in _LAWS.items() if re.search(pattern, q))
    return [provisions, laws]


def _scope(client, org_id: str | None) -> str:
    return f"corpus={client.get(CORPUS_VERSION_KEY) or '0'}|org={org_id or ''}"


def _cache_key(client, question: str, *, org_id: str | None = None) -> str:
    norm = " ".join(question.lower().split())
    return f"juris:qa:{hashlib.sha256(f'{norm}|{_scope(client, org_id)}'.encode()).hexdigest()}"


def _index_key(client, org_id: str | None) -> str:
    return f"juris:qa:sem:{hashlib.sha256(_scope(client, org_id).encode()).hexdigest()}"


def _usable(use_law_corpus: bool, document_id: str | None) -> bool:
    return settings.query_cache_enabled and use_law_corpus and not document_id


def bump_corpus_version() -> None:
    """Make every cached answer unreachable; called when a law corpus source finishes ingesting."""
    try:
        _client().incr(CORPUS_VERSION_KEY)
    except Exception:
        logger.warning("Could not bump the corpus version; cached answers may be stale for up to the TTL", exc_info=True)


def _semantic_lookup(client, question: str, vector_fn, org_id: str | None) -> dict | None:
    entries = client.lrange(_index_key(client, org_id), 0, -1)
    signature = cache_signature(question)
    candidates = [e for e in (json.loads(raw) for raw in entries) if e["sig"] == signature]
    if not candidates:
        return None  # nothing to compare with, so no embedding is computed
    vector = vector_fn()
    best, best_sim = None, settings.semantic_cache_threshold
    for entry in candidates:
        cached_vec = np.frombuffer(base64.b64decode(entry["vec"]), dtype=np.float32)
        sim = float(cached_vec @ vector)
        if sim >= best_sim:
            best, best_sim = entry, sim
    if best is None:
        return None
    raw = client.get(best["key"])
    if not raw:
        return None
    return {**json.loads(raw), "cache_match": {"question": best["q"], "similarity": round(best_sim, 4)}}


def get_cached_answer(
    question: str,
    *,
    use_law_corpus: bool,
    document_id: str | None,
    org_id: str | None = None,
    vector_fn=None,
) -> dict | None:
    """An exact hit, else a semantic one. ``vector_fn`` returns the question's normalised embedding when needed."""
    if not _usable(use_law_corpus, document_id):
        return None
    try:
        client = _client()
        raw = client.get(_cache_key(client, question, org_id=org_id))
        if raw:
            _CACHE_STATS["hits"] += 1
            return json.loads(raw)
        if settings.semantic_cache_enabled and vector_fn is not None:
            hit = _semantic_lookup(client, question, vector_fn, org_id)
            if hit:
                _CACHE_STATS["semantic_hits"] += 1
                return hit
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
    org_id: str | None = None,
    vector_fn=None,
) -> None:
    if not _usable(use_law_corpus, document_id):
        return
    try:
        client = _client()
        key = _cache_key(client, question, org_id=org_id)
        client.setex(key, settings.query_cache_ttl_seconds, json.dumps(payload))
        if settings.semantic_cache_enabled and vector_fn is not None:
            vector = vector_fn()
            index = _index_key(client, org_id)
            entry = {"q": question, "sig": cache_signature(question), "key": key,
                     "vec": base64.b64encode(np.asarray(vector, dtype=np.float32).tobytes()).decode()}
            client.lpush(index, json.dumps(entry))
            client.ltrim(index, 0, settings.semantic_cache_max_entries - 1)
            client.expire(index, settings.query_cache_ttl_seconds)
    except Exception:
        logger.warning("Query cache write failed", exc_info=True)

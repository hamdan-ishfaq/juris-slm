"""Query enhancement for legal RAG — adaptive HyDE, expansion, CRAG-lite rewrite."""
from __future__ import annotations

import re

from config import settings

_VAGUE_WORD_THRESHOLD = 12


def expand_legal_query(question: str) -> str:
    """Expand article/section references for BM25 hybrid branch (exact-token recall)."""
    q = question.strip()
    extras: list[str] = []

    art = re.search(r"(?:article|art\.?)\s*(\d+)", q, re.IGNORECASE)
    if art:
        n = art.group(1)
        extras.extend([f"Article {n}", f"Art. {n}", f"GDPR Article {n}"])

    sec = re.search(r"(?:section|§|sec\.)\s*(\d+)", q, re.IGNORECASE)
    if sec:
        n = sec.group(1)
        extras.extend([f"Section {n}", f"§ {n}", f"BGB Section {n}"])

    lower = q.lower()
    if "processor" in lower:
        extras.extend(["data processor", "Article 28", "sub-processor"])
    if "consent" in lower:
        extras.extend(["Article 7", "valid consent"])
    if "erasure" in lower or "forgotten" in lower:
        extras.extend(["Article 17", "right to erasure"])
    if "lawful" in lower and "basis" in lower:
        extras.extend(["Article 6", "lawful basis", "legal basis"])

    if not extras:
        return q
    return f"{q} {' '.join(dict.fromkeys(extras))}"


def adaptive_use_hyde(question: str, *, use_hyde: bool) -> bool:
    """HyPA-RAG style: enable HyDE for vague queries; skip when article is explicit."""
    if settings.is_airgap_latency_profile and not use_hyde and not settings.hyde_enabled:
        return False
    if use_hyde or settings.hyde_enabled:
        return True
    if not settings.adaptive_hyde_enabled:
        return False
    if _query_has_explicit_article(question):
        return False
    words = [w for w in question.split() if w]
    return len(words) <= _VAGUE_WORD_THRESHOLD


def _query_has_explicit_article(question: str) -> bool:
    return bool(re.search(r"(?:article|art\.?)\s*\d+", question, re.IGNORECASE))


def crag_rewrite_query(question: str) -> str:
    """CRAG-lite: rewrite weak-retrieval queries once before retry."""
    expanded = expand_legal_query(question)
    if expanded != question:
        return expanded
    lower = question.lower()
    if "gdpr" not in lower and re.search(r"\b(article|art\.?)\s*\d+", question, re.IGNORECASE):
        return f"{question} GDPR regulation"
    if "bgb" not in lower and re.search(r"(?:section|§)\s*\d+", question, re.IGNORECASE):
        return f"{question} BGB German Civil Code"
    return f"{question} legal obligations requirements"

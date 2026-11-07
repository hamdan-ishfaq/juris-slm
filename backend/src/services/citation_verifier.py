"""Post-generation citation verification (Phase 2.6)."""
from __future__ import annotations

import re
from typing import Any

CITATION_PATTERNS = [
    re.compile(r"\bArt\.?\s*\d+(?:\(\d+\))?", re.IGNORECASE),
    re.compile(r"\bArticle\s+\d+(?:\(\d+\))?", re.IGNORECASE),
    re.compile(r"\bGDPR\b", re.IGNORECASE),
    re.compile(r"\bBGB\b", re.IGNORECASE),
    re.compile(r"\bSection\s+\d+", re.IGNORECASE),
    re.compile(r"§\s*\d+", re.IGNORECASE),
]

DISCLAIMER = (
    "\n\n[Note: Some citations in this answer could not be verified against retrieved sources. "
    "Please confirm against the original documents.]"
)


def extract_citations(answer: str) -> list[str]:
    found: list[str] = []
    seen: set[str] = set()
    for pattern in CITATION_PATTERNS:
        for match in pattern.finditer(answer):
            token = match.group(0).strip()
            key = token.lower()
            if key not in seen:
                seen.add(key)
                found.append(token)
    return found


def _corpus_text(sources: list[dict[str, Any]], hit_contents: list[str]) -> str:
    parts: list[str] = []
    for s in sources:
        label = s.get("label") or ""
        if label:
            parts.append(str(label))
        src = s.get("source") or ""
        if src:
            parts.append(str(src))
    parts.extend(hit_contents)
    return " ".join(parts).lower()


def _normalize_cite(token: str) -> str:
    t = token.lower().strip()
    t = re.sub(r"\s+", " ", t)
    t = t.replace("art.", "article ")
    return t


def verify_citations(
    answer: str,
    sources: list[dict[str, Any]],
    hit_contents: list[str] | None = None,
) -> tuple[str, bool]:
    """
    Verify cited labels appear in source metadata or chunk text.
    Returns (possibly amended answer, all_verified).
    """
    citations = extract_citations(answer)
    if not citations:
        return answer, True

    corpus = _corpus_text(sources, hit_contents or [])
    missing: list[str] = []
    for cite in citations:
        norm = _normalize_cite(cite)
        found = norm in _normalize_cite(corpus)
        if not found:
            num = re.search(r"\d+", cite)
            if num and num.group(0) in corpus:
                found = True
        if not found:
            missing.append(cite)

    if not missing:
        return answer, True
    return answer + DISCLAIMER, False

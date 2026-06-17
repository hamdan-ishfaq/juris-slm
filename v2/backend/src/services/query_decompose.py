"""Rule-based query decomposition for compare/analyze (Phase 2.8)."""
from __future__ import annotations

import re


def decompose_for_compare(question: str) -> list[str]:
    """
    Split a complex compare question into sub-queries for multi-retrieval RRF merge.
    Always includes the original question plus regulatory baseline angles.
    """
    base = question.strip()
    subs = [base]

    lower = base.lower()
    if "gdpr" not in lower:
        subs.append("GDPR lawful processing personal data compliance requirements")
    if "bgb" not in lower and "contract" in lower:
        subs.append("BGB German civil code contractual obligations liability")
    if "deviation" in lower or "compare" in lower or "non-compliance" in lower:
        subs.append("material deviations non-compliance risks regulatory baseline")

    # Deduplicate while preserving order
    seen: set[str] = set()
    unique: list[str] = []
    for q in subs:
        key = q.lower()
        if key not in seen:
            seen.add(key)
            unique.append(q)
    return unique[:4]


def decompose_general(question: str, *, max_subs: int = 3) -> list[str]:
    """Light decomposition on sentence boundaries for long questions."""
    sentences = [s.strip() for s in re.split(r"[?;.]\s+", question) if len(s.strip()) > 20]
    if len(sentences) <= 1:
        return [question.strip()]
    out = [question.strip(), *sentences[: max_subs - 1]]
    seen: set[str] = set()
    unique: list[str] = []
    for q in out:
        key = q.lower()
        if key not in seen:
            seen.add(key)
            unique.append(q)
    return unique

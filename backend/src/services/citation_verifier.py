"""Check that the provisions an answer cites were among the retrieved chunks."""
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

# "Art. 6", "Article 6(1)", "Artikel 6", "Section 26", "§ 26". A bare number is never a citation.
_REFERENCE = re.compile(r"\b(?:art(?:icle|ikel|\.)?|section|sec\.)\s*(\d+[a-z]?)\b|§§?\s*(\d+[a-z]?)\b", re.IGNORECASE)
# Law names as they appear in answers, keyed by the law corpus's source tag.
_LAW_NAMES = {
    "gdpr": ("gdpr", "dsgvo", "general data protection regulation"),
    "bgb": ("bgb", "civil code", "bürgerliches gesetzbuch"),
    "bdsg": ("bdsg", "bundesdatenschutzgesetz", "federal data protection act"),
    "eu_ai_act": ("ai act", "ki-verordnung", "artificial intelligence act"),
}
# How far from a reference to look for the law's name: "GDPR Art. 6" and "§ 26 BDSG" both put it close by.
_LAW_WINDOW = 25


def extract_citations(answer: str) -> list[str]:
    found: list[str] = []
    seen: set[str] = set()
    for pattern in CITATION_PATTERNS:
        for match in pattern.finditer(answer):
            token = match.group(0).strip()
            if token.lower() not in seen:
                seen.add(token.lower())
                found.append(token)
    return found


def _law_near(text: str, start: int, end: int) -> str | None:
    window = text[max(0, start - _LAW_WINDOW) : end + _LAW_WINDOW].lower()
    hits = [(window.find(name), law) for law, names in _LAW_NAMES.items() for name in names if name in window]
    return min(hits)[1] if hits else None


def _references(answer: str) -> list[tuple[str | None, str]]:
    refs = []
    for match in _REFERENCE.finditer(answer):
        number = (match.group(1) or match.group(2)).lower()
        refs.append((_law_near(answer, match.start(), match.end()), number))
    return list(dict.fromkeys(refs))


def _supported(law: str | None, number: str, hits: list[dict[str, Any]]) -> bool:
    for hit in hits:
        meta = hit.get("metadata") or {}
        source = meta.get("source")
        if law and source in _LAW_NAMES and source != law:
            continue
        if str(meta.get("article") or "").lower() == number:
            return True
        # Chunks without article tags, such as contracts, must name the provision in their text.
        if re.search(rf"\b(?:art(?:icle|ikel|\.)?|section|sec\.)\s*{number}\b|§§?\s*{number}\b", hit.get("content") or "", re.I):
            return True
    return False


def verify_citations(
    answer: str,
    sources: list[dict[str, Any]],
    hit_contents: list[str] | None = None,
    *,
    hits: list[dict[str, Any]] | None = None,
) -> tuple[str, bool]:
    """Return the answer, with a note if any cited provision wasn't retrieved, and whether all were.

    A citation is verified when a retrieved chunk is tagged with that article for the same law, or names that provision in its
    text. A number appearing elsewhere doesn't count.
    """
    chunks = hits if hits is not None else [{"content": text, "metadata": {}} for text in hit_contents or []]
    for source in sources:
        chunks = chunks + [{"content": f"{source.get('label') or ''} {source.get('source') or ''}", "metadata": {}}]
    missing = [ref for ref in _references(answer) if not _supported(*ref, chunks)]
    if not missing:
        return answer, True
    return answer + DISCLAIMER, False

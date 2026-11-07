"""Phase 9F — clause extraction from contract text."""
from __future__ import annotations

import re
from typing import Any


_CLAUSE_HEADER = re.compile(
    r"^(?:"
    r"(?:article|section|clause|art\.?|§)\s+\d+[a-z]?(?:\.\d+)*"
    r"|(?:\d+\.)+\s+[A-Z]"
    r"|[A-Z][A-Z0-9\s/&\-]{4,60}$"
    r")",
    re.IGNORECASE | re.MULTILINE,
)


def extract_clauses(text: str) -> list[dict[str, Any]]:
    """Split contract text into clause blocks with stable ids."""
    text = (text or "").strip()
    if not text:
        return []

    matches = list(_CLAUSE_HEADER.finditer(text))
    if not matches:
        paragraphs = [p.strip() for p in re.split(r"\n\s*\n", text) if p.strip()]
        return [
            {
                "id": f"clause-{i + 1}",
                "title": (p.split("\n", 1)[0][:80] if p else f"Clause {i + 1}"),
                "start": 0,
                "end": len(p),
                "text": p[:4000],
            }
            for i, p in enumerate(paragraphs[:40])
        ]

    clauses: list[dict[str, Any]] = []
    for i, match in enumerate(matches):
        start = match.start()
        end = matches[i + 1].start() if i + 1 < len(matches) else len(text)
        block = text[start:end].strip()
        title = block.split("\n", 1)[0].strip()[:120] or f"Clause {i + 1}"
        clauses.append(
            {
                "id": f"clause-{i + 1}",
                "title": title,
                "start": start,
                "end": end,
                "text": block[:4000],
            }
        )
    return clauses[:50]

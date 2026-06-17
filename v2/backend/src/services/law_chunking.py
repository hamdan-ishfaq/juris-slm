"""Structure-aware chunking for GDPR/BGB law texts (Phase 2.3)."""
from __future__ import annotations

import re
from typing import Any

ARTICLE_HEADER = re.compile(
    r"^(?:Article|Art\.?)\s+(\d+)(?:\([^)]+\))?(?:\s*[-–—]\s*(.+))?$",
    re.IGNORECASE | re.MULTILINE,
)
SECTION_HEADER = re.compile(
    r"^(?:Section|§)\s*(\d+)(?:\([^)]+\))?(?:\s*[-–—]\s*(.+))?$",
    re.IGNORECASE | re.MULTILINE,
)


def _split_paragraphs(text: str, max_chars: int = 1200) -> list[str]:
    parts = re.split(r"\n\n+", text.strip())
    chunks: list[str] = []
    buf = ""
    for part in parts:
        part = part.strip()
        if not part:
            continue
        if len(buf) + len(part) + 2 <= max_chars:
            buf = f"{buf}\n\n{part}".strip() if buf else part
        else:
            if buf:
                chunks.append(buf)
            if len(part) <= max_chars:
                buf = part
            else:
                for i in range(0, len(part), max_chars):
                    chunks.append(part[i : i + max_chars])
                buf = ""
    if buf:
        chunks.append(buf)
    return chunks


def chunk_law_text(text: str, *, source: str, title: str, max_chars: int = 1200) -> list[dict[str, Any]]:
    """
    Split law text on Article/Section boundaries, then paragraph-merge to max_chars.
    Returns dicts with ``content`` and law metadata (article, paragraph, title).
    """
    text = re.sub(r"\n{3,}", "\n\n", text.strip())
    if not text:
        return []

    boundaries: list[tuple[int, str | None, str | None]] = [(0, None, None)]
    for match in ARTICLE_HEADER.finditer(text):
        boundaries.append((match.start(), match.group(1), match.group(2)))
    if len(boundaries) == 1:
        for match in SECTION_HEADER.finditer(text):
            boundaries.append((match.start(), match.group(1), match.group(2)))

    boundaries.sort(key=lambda x: x[0])
    if len(boundaries) == 1:
        return [
            {
                "content": c,
                "metadata": {"article": None, "paragraph": None, "section_title": None},
            }
            for c in _split_paragraphs(text, max_chars)
        ]

    sections: list[tuple[str, dict[str, Any]]] = []
    for i, (start, num, heading) in enumerate(boundaries):
        end = boundaries[i + 1][0] if i + 1 < len(boundaries) else len(text)
        block = text[start:end].strip()
        if not block:
            continue
        meta: dict[str, Any] = {
            "article": num,
            "paragraph": None,
            "section_title": (heading or "").strip() or None,
        }
        sections.append((block, meta))

    out: list[dict[str, Any]] = []
    for block, base_meta in sections:
        for para in _split_paragraphs(block, max_chars):
            out.append({"content": para, "metadata": dict(base_meta)})
    return out

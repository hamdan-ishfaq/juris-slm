"""Structure-aware chunking for GDPR/BGB law texts (Phase 2.3)."""
from __future__ import annotations

import re
from typing import Any

ARTICLE_HEADER = re.compile(
    r"^(?:Article|Art\.?)\s+(\d+)(?:\([^)]+\))?(?:\s*[-–—]\s*(.+))?$",
    re.IGNORECASE | re.MULTILINE,
)
# "Section 437", "§ 26 - Title" or "§ 26 Title". A title starts with a capital and has no closing
# punctuation, so a sentence such as "§ 4 gilt entsprechend." stays body text.
SECTION_HEADER = re.compile(
    r"^(?:Section|§)\s*(\d+[a-z]?)(?:\([^)]+\))?(?:\s*[-–—]\s*(.+)|[ \t]+([A-ZÄÖÜ][^\n]{0,298}[^.;:,\n]))?$",
    re.MULTILINE,
)
ANNEX_HEADER = re.compile(r"^ANNEX\s+([IVXLC]+)$", re.MULTILINE)
_MAX_TITLE_CHARS = 120
_MIN_CHUNK_CHARS = 120


# Navigation text left in the BGB source; alone it became a chunk that ranks first for vague questions.
_NAVIGATION = re.compile(r"^table of contents$", re.IGNORECASE)


def _normalise(text: str) -> str:
    lines = [line.replace("\xa0", " ").strip() for line in text.splitlines()]
    lines = [line for line in lines if not _NAVIGATION.match(line)]
    return re.sub(r"\n{3,}", "\n\n", "\n".join(lines)).strip()


def _split_long(part: str, max_chars: int) -> list[str]:
    """Cut an over-long paragraph after a sentence, or failing that a space, never inside a word. A tail too short to mean
    anything on its own joins the piece before it."""
    pieces: list[str] = []
    rest = part
    while len(rest) > max_chars:
        window = rest[:max_chars]
        cut = max(window.rfind(". "), window.rfind("; "), window.rfind(": "))
        cut = cut + 1 if cut >= _MIN_CHUNK_CHARS else window.rfind(" ")
        if cut < _MIN_CHUNK_CHARS:
            cut = max_chars
        pieces.append(rest[:cut].strip())
        rest = rest[cut:].strip()
    if rest:
        if pieces and len(rest) < _MIN_CHUNK_CHARS:
            pieces[-1] = f"{pieces[-1]} {rest}"
        else:
            pieces.append(rest)
    return pieces


def _title_and_body(block: str, heading: str | None) -> tuple[str | None, str]:
    """A bare header may have its title on the next line. Return the title and the text below both."""
    below = [line for line in block.split("\n")[1:] if line]
    if heading:
        return heading.strip(), "\n".join(below)
    if below and len(below[0]) <= _MAX_TITLE_CHARS and not below[0].endswith((".", ";", ":", ",")):
        return below[0], "\n".join(below[1:])
    return None, "\n".join(below)


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
            continue
        # A heading or list number means nothing alone, so it stays with the text after it.
        if buf and len(buf) < _MIN_CHUNK_CHARS:
            part = f"{buf}\n\n{part}"
        elif buf:
            chunks.append(buf)
        buf = ""
        if len(part) <= max_chars:
            buf = part
        else:
            chunks.extend(_split_long(part, max_chars))
    if buf:
        chunks.append(buf)
    return chunks


def chunk_law_text(text: str, *, source: str, title: str, max_chars: int = 1200) -> list[dict[str, Any]]:
    """
    Split law text on Article/Section boundaries, then paragraph-merge to max_chars.
    Returns dicts with ``content`` and law metadata (article, paragraph, title).
    """
    text = _normalise(text)
    if not text:
        return []

    boundaries: list[tuple[int, str | None, str | None]] = [(0, None, None)]
    for match in ARTICLE_HEADER.finditer(text):
        boundaries.append((match.start(), match.group(1), match.group(2)))
    # Without its own boundary, an annex would be labelled as the last article.
    for match in ANNEX_HEADER.finditer(text):
        boundaries.append((match.start(), f"Annex {match.group(1)}", None))
    if len(boundaries) == 1:
        for match in SECTION_HEADER.finditer(text):
            boundaries.append((match.start(), match.group(1), match.group(2) or match.group(3)))

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
        title = None
        if num is not None:
            title, body = _title_and_body(block, heading)
            # A header with no text under it is a table of contents entry.
            if not body:
                continue
        meta: dict[str, Any] = {"article": num, "paragraph": None, "section_title": title}
        sections.append((block, meta))

    out: list[dict[str, Any]] = []
    for block, base_meta in sections:
        for para in _split_paragraphs(block, max_chars):
            out.append({"content": para, "metadata": dict(base_meta)})
    return out

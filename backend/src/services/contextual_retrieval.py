"""Anthropic-style contextual prefixes applied at embedding time (Phase 2.4)."""
from __future__ import annotations

import re
from typing import Any
from urllib.parse import unquote


def _document_name(title: str) -> str:
    """Filenames often use separators where a name has spaces: "Acme_Corp-NDA.pdf" becomes "Acme Corp NDA"."""
    stem = unquote(title.replace("\\", "/").rsplit("/", 1)[-1]).rsplit(".", 1)[0]
    return re.sub(r"[_\-]+", " ", stem)


def build_embedding_text(content: str, metadata: dict[str, Any]) -> str:
    """Return text to embed; raw ``content`` is still stored for display."""
    kind = metadata.get("kind", "")
    if kind == "law":
        title = metadata.get("title") or metadata.get("source") or "law corpus"
        article = metadata.get("article")
        paragraph = metadata.get("paragraph")
        label_parts = [f"This chunk is from {title}"]
        if article:
            art_label = f"Article {article}"
            if paragraph:
                art_label += f"({paragraph})"
            label_parts.append(art_label)
        prefix = " ".join(label_parts) + "."
        return f"{prefix}\n\n{content}"
    if kind == "contract":
        parts = []
        if metadata.get("title"):
            parts.append(f"This is from the document: {_document_name(metadata['title'])}.")
        section = metadata.get("section_title") or metadata.get("parent_title")
        if section:
            parts.append(f"This clause is from section: {section}.")
        return "\n\n".join([*parts, content])
    return content

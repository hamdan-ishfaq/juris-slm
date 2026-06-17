"""Anthropic-style contextual prefixes applied at embedding time (Phase 2.4)."""
from __future__ import annotations

from typing import Any


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
        section = metadata.get("section_title") or metadata.get("parent_title")
        if section:
            return f"This clause is from section: {section}.\n\n{content}"
    return content

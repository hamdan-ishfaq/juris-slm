from __future__ import annotations

import re
from typing import Any


def hierarchical_chunk(text: str, *, child_max: int = 600) -> list[dict[str, Any]]:
    """
    Parent-child chunking for contracts (Phase 2.7).
    Parent = section block; child = paragraph-sized retrieval unit (~600 chars).
    """
    text = re.sub(r"\n{3,}", "\n\n", text.strip())
    if not text:
        return []

    section_pattern = re.compile(
        r"\n(?=(?:Article|Section|ARTICLE|SECTION)\s+\d+|(?:\d+\.\s+[A-Z][A-Za-z\s]{2,40})\n)",
        re.IGNORECASE,
    )
    sections = section_pattern.split(text)
    if len(sections) <= 1:
        sections = [text]

    chunks: list[dict[str, Any]] = []
    parent_idx = 0
    for section in sections:
        section = section.strip()
        if not section:
            continue
        parent_id = f"parent-{parent_idx}"
        parent_title = section.split("\n", 1)[0].strip()[:120]
        parent_idx += 1

        paragraphs = re.split(r"\n\n+", section)
        child_idx = 0
        for para in paragraphs:
            para = para.strip()
            if len(para) < 50:
                continue
            if len(para) <= child_max:
                chunks.append(
                    {
                        "content": para,
                        "parent_content": section,
                        "parent_id": parent_id,
                        "parent_title": parent_title,
                        "child_index": child_idx,
                    }
                )
                child_idx += 1
            else:
                for i in range(0, len(para), child_max):
                    sub = para[i : i + child_max].strip()
                    if len(sub) >= 50:
                        chunks.append(
                            {
                                "content": sub,
                                "parent_content": section,
                                "parent_id": parent_id,
                                "parent_title": parent_title,
                                "child_index": child_idx,
                            }
                        )
                        child_idx += 1
    return chunks

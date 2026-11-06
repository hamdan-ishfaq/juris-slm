"""Deterministic Legal Graph — rule-based GDPR/BGB article edges (Phase 5)."""
from __future__ import annotations

import re
from typing import Any

import uuid

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

# Known cross-references in GDPR/BGB ingest (expand over time)
_GDPR_EDGES: list[tuple[str, str, str]] = [
    ("Art. 6", "Art. 7", "RELATES_TO"),
    ("Art. 6", "Art. 28", "PROCESSOR"),
    ("Art. 6", "Art. 88", "EMPLOYMENT"),
    ("Art. 5", "Art. 25", "DATA_PROTECTION_BY_DESIGN"),
    ("Art. 13", "Art. 14", "INFORMATION_DUTY"),
]


async def ensure_dlg_law_edges(db: AsyncSession) -> int:
    """Insert deterministic law-corpus graph edges if missing. Returns count created."""
    created = 0
    for src, tgt, rel in _GDPR_EDGES:
        src_chunks = await _find_law_chunks(db, src)
        tgt_chunks = await _find_law_chunks(db, tgt)
        if not src_chunks or not tgt_chunks:
            continue
        for s in src_chunks[:2]:
            for t in tgt_chunks[:2]:
                ok = await _insert_dlg_edge(db, s, t, rel)
                if ok:
                    created += 1
    await db.commit()
    return created


async def _find_law_chunks(db: AsyncSession, article_label: str) -> list[dict[str, Any]]:
    num = re.search(r"(\d+)", article_label)
    if not num:
        return []
    n = num.group(1)
    sql = text(
        """
        SELECT id, content, metadata
        FROM document_chunks
        WHERE metadata->>'kind' = 'law'
          AND (content ILIKE :p1 OR content ILIKE :p2)
        LIMIT 3
        """
    )
    rows = await db.execute(
        sql,
        {"p1": f"%Article {n}%", "p2": f"%Art. {n}%"},
    )
    return [dict(r) for r in rows.mappings()]


async def _insert_dlg_edge(db: AsyncSession, src: dict, tgt: dict, rel: str) -> bool:
    """Store DLG edge in metadata sidecar table via audit-style JSON in chunk metadata."""
    # Lightweight: append dlg_refs to source chunk metadata
    meta = src.get("metadata") or {}
    if isinstance(meta, str):
        import json

        meta = json.loads(meta)
    refs = list(meta.get("dlg_refs") or [])
    ref = {"target_chunk_id": src["id"], "to_article": rel, "edge": rel}
    if ref in refs:
        return False
    refs.append(ref)
    meta["dlg_refs"] = refs
    import json

    await db.execute(
        text("UPDATE document_chunks SET metadata = CAST(:meta AS jsonb) WHERE id = :id"),
        {"meta": json.dumps(meta), "id": src["id"]},
    )
    return True


async def fetch_dlg_context(db: AsyncSession, question: str) -> str:
    """Return supplemental deterministic graph context for law queries."""
    articles = re.findall(r"(?:article|art\.?)\s*(\d+)", question, re.IGNORECASE)
    if not articles:
        return ""
    parts: list[str] = []
    for n in articles[:3]:
        chunks = await _find_law_chunks(db, f"Art. {n}")
        for c in chunks[:1]:
            parts.append(c.get("content", "")[:400])
    if not parts:
        return ""
    return "\n\n[DLG CONTEXT]\n" + "\n---\n".join(parts)

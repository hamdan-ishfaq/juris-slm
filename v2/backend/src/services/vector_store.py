from __future__ import annotations

import json
import uuid
from typing import Any

import numpy as np
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from config import settings
from services.access_control import can_access_confidentiality


def _vector_literal(vec: np.ndarray) -> str:
    return "[" + ",".join(f"{x:.8f}" for x in vec.tolist()) + "]"


async def insert_chunk(
    db: AsyncSession,
    *,
    document_id: uuid.UUID,
    chunk_index: int,
    content: str,
    embedding: np.ndarray,
    metadata: dict[str, Any],
) -> None:
    await db.execute(
        text(
            """
            INSERT INTO document_chunks (document_id, chunk_index, content, embedding, metadata)
            VALUES (:document_id, :chunk_index, :content, CAST(:embedding AS vector), CAST(:metadata AS jsonb))
            """
        ),
        {
            "document_id": str(document_id),
            "chunk_index": chunk_index,
            "content": content,
            "embedding": _vector_literal(embedding),
            "metadata": json.dumps(metadata),
        },
    )


async def delete_by_document_id(db: AsyncSession, document_id: uuid.UUID) -> int:
    result = await db.execute(
        text("DELETE FROM document_chunks WHERE document_id = :doc_id"),
        {"doc_id": str(document_id)},
    )
    return result.rowcount or 0


async def search_similar(
    db: AsyncSession,
    query_embedding: np.ndarray,
    *,
    top_k: int | None = None,
    accessible_document_ids: set[uuid.UUID] | None = None,
    include_law_corpus: bool = False,
    user_role: str = "member",
    document_id: uuid.UUID | None = None,
    filters: dict[str, Any] | None = None,
) -> list[dict[str, Any]]:
    """Vector search with retrieval-layer RBAC (Phase 1)."""
    k = top_k or settings.rag_top_k
    params: dict[str, Any] = {
        "q": _vector_literal(query_embedding),
        "k": k,
        "include_law": include_law_corpus,
        "user_role": user_role,
    }

    conditions: list[str] = []
    access_parts: list[str] = []

    if include_law_corpus:
        access_parts.append("metadata->>'kind' = 'law'")

    if accessible_document_ids:
        params["doc_ids"] = [str(d) for d in accessible_document_ids]
        access_parts.append("document_id = ANY(CAST(:doc_ids AS uuid[]))")

    if not access_parts:
        return []

    conditions.append("(" + " OR ".join(access_parts) + ")")

    if document_id is not None:
        params["single_doc_id"] = str(document_id)
        conditions.append("document_id = CAST(:single_doc_id AS uuid)")

    # Confidentiality: law corpus exempt; matter docs filtered by role
    conditions.append(
        """(
            metadata->>'kind' = 'law'
            OR COALESCE(metadata->>'confidentiality', 'internal') = 'internal'
            OR (:user_role IN ('matter_lead', 'org_admin', 'owner')
                AND COALESCE(metadata->>'confidentiality', 'internal') = 'restricted')
            OR (:user_role IN ('org_admin', 'owner')
                AND COALESCE(metadata->>'confidentiality', 'internal') = 'privileged')
        )"""
    )

    if filters:
        for key, value in filters.items():
            if key in ("document_id", "kind"):
                continue
            param_key = f"filter_{key}"
            conditions.append(f"metadata->>'{key}' = :{param_key}")
            params[param_key] = str(value)

    sql = """
        SELECT id, content, metadata,
               (embedding <=> CAST(:q AS vector)) AS distance
        FROM document_chunks
        WHERE """ + " AND ".join(conditions) + """
        ORDER BY distance ASC
        LIMIT :k
    """
    rows = await db.execute(text(sql), params)
    out = []
    for row in rows.mappings():
        meta = row["metadata"]
        if isinstance(meta, str):
            meta = json.loads(meta)
        meta = meta or {}
        conf = meta.get("confidentiality", "internal")
        kind = meta.get("kind")
        if kind != "law" and not can_access_confidentiality(user_role, conf):
            continue
        out.append(
            {
                "id": row["id"],
                "content": row["content"],
                "metadata": meta,
                "distance": float(row["distance"]),
            }
        )
    return out


async def corpus_stats(db: AsyncSession) -> dict[str, Any]:
    total = await db.execute(text("SELECT COUNT(*) AS c FROM document_chunks"))
    count = int(total.scalar_one())
    by_source_rows = await db.execute(
        text(
            """
            SELECT COALESCE(metadata->>'source', 'unknown') AS source, COUNT(*) AS c
            FROM document_chunks
            GROUP BY 1
            ORDER BY 2 DESC
            """
        )
    )
    by_source = {r["source"]: int(r["c"]) for r in by_source_rows.mappings()}
    return {"total_chunks": count, "by_source": by_source}


async def fetch_graph_context(db: AsyncSession, query: str, document_id: str) -> str:
    words = [w.lower() for w in query.split() if len(w) > 3]
    if not words:
        return ""

    conditions = " OR ".join([f"LOWER(n.name) LIKE :w{i}" for i in range(len(words))])
    params = {f"w{i}": f"%{w}%" for i, w in enumerate(words)}
    params["doc_id"] = document_id

    sql = f"""
        SELECT DISTINCT dc.content
        FROM graph_nodes n
        JOIN graph_edges e ON (n.id = e.source_node_id OR n.id = e.target_node_id)
        JOIN document_chunks dc ON (dc.document_id = n.document_id AND dc.chunk_index = e.chunk_index)
        WHERE n.document_id = CAST(:doc_id AS UUID) AND ({conditions})
        LIMIT 3
    """
    rows = await db.execute(text(sql), params)
    graph_chunks = [row[0] for row in rows]
    if graph_chunks:
        return "\n\n[GRAPH CONTEXT]\n" + "\n\n".join(graph_chunks)
    return ""

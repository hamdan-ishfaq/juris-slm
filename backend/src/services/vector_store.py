from __future__ import annotations

import json
import re
import uuid
from typing import Any

import numpy as np
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from config import settings
from services.access_control import can_access_confidentiality
from services.rrf import rrf_merge


def _vector_literal(vec: np.ndarray) -> str:
    return "[" + ",".join(f"{x:.8f}" for x in vec.tolist()) + "]"


# Citations such as "Art. 6", "Artikel 6", "Section 26" or "§ 26".
_LEGAL_REFERENCE = re.compile(
    r"(?:\bart(?:icles?|ikel|\.)?|\bsec(?:tions?|\.)?|\bparagraphs?|§§?)\s*\d+[a-z]?\b", re.IGNORECASE
)
# The 'simple' text search config keeps stopwords, and in an OR query they would match almost every chunk.
_KEYWORD_STOPWORDS = frozenset(
    """a an and are as at be but by can do does for from has have how i if in into is it its may me must my no not
    of on or our shall should so such that the their them then there these they this to under was we were what when
    where which who whom why will with would you your der die das und oder ein eine ist im zu von mit""".split()
)


def has_legal_reference(query_text: str) -> bool:
    return bool(_LEGAL_REFERENCE.search(query_text))


def cited_provisions(query_text: str) -> set[str]:
    """The numbers of provisions a question cites, in the form chunk metadata stores them."""
    return {re.search(r"\d+[a-z]?", match.group()).group() for match in _LEGAL_REFERENCE.finditer(query_text)}


def _or_tsquery(query_text: str) -> str:
    """Build a to_tsquery string matching any meaningful term. Requiring all of them matched nothing."""
    tokens = [
        token
        for token in re.findall(r"\w+", query_text.lower())
        if token not in _KEYWORD_STOPWORDS and (len(token) > 1 or token.isdigit())
    ]
    return " | ".join(f"'{token}'" for token in dict.fromkeys(tokens))


def _build_access_sql(
    *,
    accessible_document_ids: set[uuid.UUID] | None,
    include_law_corpus: bool,
    user_role: str,
    document_id: uuid.UUID | None,
    filters: dict[str, Any] | None,
    params: dict[str, Any],
    org_id: uuid.UUID | None = None,
) -> tuple[list[str], dict[str, Any]]:
    conditions: list[str] = []
    access_parts: list[str] = []

    if include_law_corpus:
        # Statutes have no org_id and are shared. A corpus an org uploaded carries its org_id and stays private.
        if org_id is None:
            access_parts.append("(metadata->>'kind' = 'law' AND metadata->>'org_id' IS NULL)")
        else:
            access_parts.append(
                "(metadata->>'kind' = 'law' AND (metadata->>'org_id' IS NULL OR metadata->>'org_id' = :org_id))"
            )
            params["org_id"] = str(org_id)

    if accessible_document_ids:
        params["doc_ids"] = [str(d) for d in accessible_document_ids]
        access_parts.append("document_id = ANY(CAST(:doc_ids AS uuid[]))")

    if not access_parts:
        return [], params

    conditions.append("(" + " OR ".join(access_parts) + ")")

    if org_id is not None:
        conditions.append("(metadata->>'org_id' = :org_id OR metadata->>'org_id' IS NULL)")
        params["org_id"] = str(org_id)

    if document_id is not None:
        params["single_doc_id"] = str(document_id)
        conditions.append("document_id = CAST(:single_doc_id AS uuid)")

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

    return conditions, params


def _post_filter_hits(rows, user_role: str) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    for row in rows:
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
                "distance": float(row.get("distance", 1.0)),
            }
        )
    return out


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
    org_id: uuid.UUID | None = None,
) -> list[dict[str, Any]]:
    """Vector-only search with retrieval-layer RBAC (Phase 1) + org isolation (Phase 9A)."""
    k = top_k or settings.rag_top_k
    params: dict[str, Any] = {
        "q": _vector_literal(query_embedding),
        "k": k,
        "user_role": user_role,
    }

    conditions, params = _build_access_sql(
        accessible_document_ids=accessible_document_ids,
        include_law_corpus=include_law_corpus,
        user_role=user_role,
        document_id=document_id,
        filters=filters,
        params=params,
        org_id=org_id,
    )
    if not conditions:
        return []

    sql = """
        SELECT id, content, metadata,
               (embedding <=> CAST(:q AS vector)) AS distance
        FROM document_chunks
        WHERE """ + " AND ".join(conditions) + """
        ORDER BY distance ASC
        LIMIT :k
    """
    # With an access filter, an index scan stops at ef_search candidates and can return too few rows.
    await db.execute(text("SET LOCAL hnsw.iterative_scan = strict_order"))
    rows = await db.execute(text(sql), params)
    return _post_filter_hits(rows.mappings(), user_role)


async def search_fts(
    db: AsyncSession,
    query_text: str,
    *,
    top_k: int | None = None,
    accessible_document_ids: set[uuid.UUID] | None = None,
    include_law_corpus: bool = False,
    user_role: str = "member",
    document_id: uuid.UUID | None = None,
    filters: dict[str, Any] | None = None,
    org_id: uuid.UUID | None = None,
) -> list[dict[str, Any]]:
    """Keyword branch: Postgres text search ranked by ts_rank. This is not BM25."""
    k = top_k or settings.rag_top_k
    fts_q = _or_tsquery(query_text)
    if not fts_q:
        return []

    params: dict[str, Any] = {
        "fts_q": fts_q,
        "k": k,
        "user_role": user_role,
    }
    conditions, params = _build_access_sql(
        accessible_document_ids=accessible_document_ids,
        include_law_corpus=include_law_corpus,
        user_role=user_role,
        document_id=document_id,
        filters=filters,
        params=params,
        org_id=org_id,
    )
    if not conditions:
        return []

    conditions.append("content_tsv @@ to_tsquery('simple', :fts_q)")

    sql = """
        SELECT id, content, metadata,
               ts_rank(content_tsv, to_tsquery('simple', :fts_q)) AS distance
        FROM document_chunks
        WHERE """ + " AND ".join(conditions) + """
        ORDER BY distance DESC
        LIMIT :k
    """
    rows = await db.execute(text(sql), params)
    hits = _post_filter_hits(rows.mappings(), user_role)
    for h in hits:
        h["distance"] = 1.0 - min(float(h.get("distance", 0)), 1.0)
    return hits


async def hybrid_search(
    db: AsyncSession,
    query_text: str,
    query_embedding: np.ndarray,
    *,
    top_k: int | None = None,
    accessible_document_ids: set[uuid.UUID] | None = None,
    include_law_corpus: bool = False,
    user_role: str = "member",
    document_id: uuid.UUID | None = None,
    filters: dict[str, Any] | None = None,
    org_id: uuid.UUID | None = None,
) -> list[dict[str, Any]]:
    """
    Vector search, merged by Reciprocal Rank Fusion with keyword search when the query cites a provision.
    Keyword results lowered recall on questions with no citation. See docs/DECISIONS.md, D-002.
    """
    k = top_k or settings.rag_top_k
    branch_k = max(k * 2, 20)

    vec_hits = await search_similar(
        db,
        query_embedding,
        top_k=branch_k,
        accessible_document_ids=accessible_document_ids,
        include_law_corpus=include_law_corpus,
        user_role=user_role,
        document_id=document_id,
        filters=filters,
        org_id=org_id,
    )

    if not settings.hybrid_search_enabled or not has_legal_reference(query_text):
        return vec_hits[:k]

    fts_hits = await search_fts(
        db,
        query_text,
        top_k=branch_k,
        accessible_document_ids=accessible_document_ids,
        include_law_corpus=include_law_corpus,
        user_role=user_role,
        document_id=document_id,
        filters=filters,
        org_id=org_id,
    )

    if not fts_hits:
        return vec_hits[:k]

    merged = rrf_merge([vec_hits, fts_hits], k=settings.rag_rrf_k, top_k=k)
    return merged if merged else vec_hits[:k]


async def corpus_stats(db: AsyncSession) -> dict[str, Any]:
    total = await db.execute(text("SELECT COUNT(*) AS c FROM document_chunks"))
    count = int(total.scalar_one())
    by_source_rows = await db.execute(
        text(
            """
            SELECT COALESCE(metadata->>'source', 'unknown') AS source, COUNT(*) AS c
            FROM document_chunks
            WHERE NOT (metadata->>'kind' = 'law' AND metadata->>'org_id' IS NOT NULL)
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

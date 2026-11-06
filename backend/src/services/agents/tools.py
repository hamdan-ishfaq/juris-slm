"""Phase 9D — fixed tool wrappers for gap analysis (no open ReAct)."""
from __future__ import annotations

import re
import uuid
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from db import DocumentChunk, MatterDocument, User
from services.embeddings import embed_texts
from services.vector_store import hybrid_search

MAX_OBLIGATIONS = 5

_OBLIGATION_PATTERNS = [
    (r"confidential", "confidentiality"),
    (r"shall not disclose|non-disclosure|nda", "confidentiality"),
    (r"personal data|data processing|processor", "data_processing"),
    (r"lawful basis|legal obligation|article 6", "lawful_basis"),
    (r"transfer|sub-processor|third countr", "international_transfer"),
    (r"terminat|expir", "termination"),
    (r"indemnif|liabilit", "liability"),
]

_LAW_QUERIES = {
    "confidentiality": "GDPR confidentiality personal data protection Article 32",
    "data_processing": "GDPR Article 28 processor obligations data processing agreement",
    "lawful_basis": "GDPR Article 6 lawful basis legal obligation processing",
    "international_transfer": "GDPR Chapter V international transfer standard contractual clauses",
    "termination": "GDPR Article 17 erasure retention storage limitation",
    "liability": "GDPR Article 82 liability damages controller processor",
}


async def extract_clauses(
    db: AsyncSession,
    *,
    document_id: uuid.UUID,
    user: User,
) -> list[dict[str, Any]]:
    """Extract obligation-bearing clauses from document chunks."""
    rows = await db.execute(
        select(DocumentChunk)
        .where(DocumentChunk.document_id == document_id)
        .order_by(DocumentChunk.chunk_index)
        .limit(40)
    )
    chunks = [{"content": c.content, "chunk_index": c.chunk_index} for c in rows.scalars().all()]
    if not chunks:
        doc = await db.get(MatterDocument, document_id)
        if doc:
            from pathlib import Path
            from services.document_parser import parse_document

            text = parse_document(Path(doc.file_path), doc.filename)
            chunks = [{"content": text, "chunk_index": 0}]

    obligations: list[dict[str, Any]] = []
    seen_topics: set[str] = set()
    for chunk in chunks:
        content = chunk.get("content") or ""
        for pat, topic in _OBLIGATION_PATTERNS:
            if topic in seen_topics:
                continue
            if re.search(pat, content, re.IGNORECASE):
                excerpt = content.strip()[:400]
                obligations.append(
                    {
                        "id": f"obl-{len(obligations)+1}",
                        "clause_text": excerpt,
                        "topic": topic,
                    }
                )
                seen_topics.add(topic)
            if len(obligations) >= MAX_OBLIGATIONS:
                break
        if len(obligations) >= MAX_OBLIGATIONS:
            break

    if not obligations and chunks:
        text = (chunks[0].get("content") or "")[:400]
        obligations.append({"id": "obl-1", "clause_text": text, "topic": "general"})
    return obligations


async def search_law(
    db: AsyncSession,
    *,
    topic: str,
    query_override: str | None,
    user: User,
) -> list[dict[str, Any]]:
    """Hybrid search against law corpus for a regulatory topic."""
    query = query_override or _LAW_QUERIES.get(topic, f"GDPR {topic.replace('_', ' ')}")
    vec = embed_texts([query])[0]
    hits = await hybrid_search(
        db,
        query,
        vec,
        top_k=3,
        accessible_document_ids=None,
        include_law_corpus=True,
        user_role=user.role,
        org_id=user.org_id,
    )
    return hits


def compare_clause(
    *,
    obligation: dict[str, Any],
    law_hits: list[dict[str, Any]],
) -> dict[str, Any]:
    """Rule-based alignment scoring between clause and law context."""
    clause = (obligation.get("clause_text") or "").lower()
    topic = obligation.get("topic", "general")
    law_ref = "GDPR (general)"
    law_text = ""
    if law_hits:
        meta = law_hits[0].get("metadata") or {}
        law_ref = meta.get("title") or meta.get("parent_title") or law_ref
        law_text = (law_hits[0].get("content") or "")[:300]

    keywords = {
        "confidentiality": ["confidential", "security", "protect", "disclosure"],
        "data_processing": ["processor", "processing", "article 28", "sub-processor"],
        "lawful_basis": ["lawful", "article 6", "legal obligation", "consent"],
        "international_transfer": ["transfer", "adequacy", "scc", "third country"],
        "termination": ["terminat", "erasure", "retention", "delete"],
        "liability": ["liabilit", "damages", "indemn"],
    }
    terms = keywords.get(topic, ["gdpr", "obligation", "shall"])
    law_lower = law_text.lower()
    hits_in_law = sum(1 for t in terms if t in law_lower)
    hits_in_clause = sum(1 for t in terms if t in clause)

    if hits_in_law >= 2 and hits_in_clause >= 1:
        severity = "aligned"
        gap = "Clause appears aligned with baseline statutory requirements."
        rec = "Document for legal review; no critical gap flagged."
    elif hits_in_law >= 1 or hits_in_clause >= 1:
        severity = "partial"
        gap = f"Partial alignment on {topic.replace('_', ' ')} — verify against {law_ref}."
        rec = "Strengthen language to mirror statutory wording; add explicit lawful basis if missing."
    else:
        severity = "missing"
        gap = f"No clear {topic.replace('_', ' ')} coverage detected against {law_ref}."
        rec = "Add explicit clause addressing this obligation or document exception in schedule."

    return {
        "obligation_id": obligation.get("id"),
        "clause_excerpt": obligation.get("clause_text", "")[:200],
        "law_reference": law_ref,
        "severity": severity,
        "gap_description": gap,
        "recommendation": rec,
        "law_excerpt": law_text[:200] if law_text else None,
    }


def finalize_report(
    *,
    document_id: uuid.UUID,
    matter_id: uuid.UUID,
    obligations: list[dict],
    gaps: list[dict],
    tool_calls: int,
    steps: list[str],
) -> dict[str, Any]:
    high = sum(1 for g in gaps if g.get("severity") in ("missing", "high"))
    partial = sum(1 for g in gaps if g.get("severity") == "partial")
    summary = (
        f"Gap analysis complete: {len(obligations)} obligations reviewed, "
        f"{high} critical/missing, {partial} partial alignments."
    )
    return {
        "document_id": str(document_id),
        "matter_id": str(matter_id),
        "obligations": obligations,
        "gaps": gaps,
        "summary": summary,
        "tool_calls_used": tool_calls,
        "steps_completed": steps,
    }

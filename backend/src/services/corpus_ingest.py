"""Shared law corpus ingest — Phase 10B."""
from __future__ import annotations

import uuid

from sqlalchemy.ext.asyncio import AsyncSession

from config import settings
from services.contextual_retrieval import build_embedding_text
from services.document_parser import parse_document
from services.embeddings import embed_texts
from services.law_chunking import chunk_law_text
from services.vector_store import delete_by_document_id, insert_chunk
from pathlib import Path


async def ingest_text_corpus(
    db: AsyncSession,
    *,
    raw_text: str,
    source: str,
    title: str,
    document_id: uuid.UUID,
    jurisdiction: str = "general",
) -> int:
    structured = chunk_law_text(raw_text, source=source, title=title)
    await delete_by_document_id(db, document_id)

    embed_inputs: list[str] = []
    metas: list[dict] = []
    contents: list[str] = []

    for item in structured:
        content = item["content"]
        meta = {
            "source": source,
            "title": title,
            "kind": "law",
            "jurisdiction": jurisdiction,
            **item.get("metadata", {}),
        }
        contents.append(content)
        metas.append(meta)
        if settings.contextual_retrieval_enabled:
            embed_inputs.append(build_embedding_text(content, meta))
        else:
            embed_inputs.append(content)

    if not contents:
        return 0

    vectors = embed_texts(embed_inputs)
    for i, (content, vec, meta) in enumerate(zip(contents, vectors, metas)):
        await insert_chunk(
            db,
            document_id=document_id,
            chunk_index=i,
            content=content,
            embedding=vec,
            metadata=meta,
        )
    return len(contents)


async def ingest_file_corpus(
    db: AsyncSession,
    *,
    file_path: Path,
    source: str,
    title: str,
    document_id: uuid.UUID,
    jurisdiction: str = "general",
) -> int:
    if file_path.suffix.lower() == ".txt":
        raw = file_path.read_text(encoding="utf-8", errors="replace")
    else:
        raw = parse_document(file_path, file_path.name)
    return await ingest_text_corpus(
        db,
        raw_text=raw,
        source=source,
        title=title,
        document_id=document_id,
        jurisdiction=jurisdiction,
    )

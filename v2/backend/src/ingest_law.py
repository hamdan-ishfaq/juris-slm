#!/usr/bin/env python3
"""Phase 2.3 — Ingest GDPR/BGB law text into pgvector. Run inside api container or locally."""
from __future__ import annotations

import asyncio
import re
import uuid
from pathlib import Path

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from config import settings
from db import async_session_factory
from services.embeddings import embed_texts
from services.vector_store import delete_by_document_id, insert_chunk

LAW_FILES = [
    ("gdpr_en.txt", "gdpr", "GDPR (English)", uuid.UUID("11111111-1111-4111-8111-111111110001")),
    ("bgb_en.txt", "bgb", "BGB (English)", uuid.UUID("11111111-1111-4111-8111-111111110002")),
]


def chunk_text(text: str, max_chars: int = 1200) -> list[str]:
    text = re.sub(r"\n{3,}", "\n\n", text.strip())
    parts = re.split(r"\n\n+", text)
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


async def ingest_file(db: AsyncSession, path: Path, source: str, title: str, document_id: uuid.UUID) -> int:
    if not path.is_file():
        print(f"  [SKIP] missing {path}")
        return 0
    text = path.read_text(encoding="utf-8", errors="replace")
    chunks = chunk_text(text)
    await delete_by_document_id(db, document_id)
    vectors = embed_texts(chunks)
    for i, (content, vec) in enumerate(zip(chunks, vectors)):
        await insert_chunk(
            db,
            document_id=document_id,
            chunk_index=i,
            content=content,
            embedding=vec,
            metadata={"source": source, "title": title, "kind": "law", "file": path.name},
        )
    await db.commit()
    print(f"  [OK] {path.name}: {len(chunks)} chunks")
    return len(chunks)


async def main() -> None:
    root = settings.law_corpus_path
    print(f"Ingesting law corpus from {root}")
    total = 0
    async with async_session_factory() as db:
        for filename, source, title, doc_id in LAW_FILES:
            total += await ingest_file(db, root / filename, source, title, doc_id)
        await db.execute(
            text(
                """
                CREATE INDEX IF NOT EXISTS idx_document_chunks_embedding_hnsw
                ON document_chunks USING hnsw (embedding vector_cosine_ops)
                """
            )
        )
        await db.commit()
    print(f"Done. Total chunks: {total}")


if __name__ == "__main__":
    asyncio.run(main())

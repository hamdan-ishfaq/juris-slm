#!/usr/bin/env python3
"""Phase 2 — Ingest GDPR/BGB law text with structure-aware + contextual embedding."""
from __future__ import annotations

import argparse
import asyncio
import uuid
from pathlib import Path

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from config import settings
from db import async_session_factory
from services.contextual_retrieval import build_embedding_text
from services.embeddings import embed_texts
from services.law_chunking import chunk_law_text
from services.vector_store import delete_by_document_id, insert_chunk

LAW_FILES = [
    ("gdpr_en.txt", "gdpr", "GDPR (English)", uuid.UUID("11111111-1111-4111-8111-111111110001")),
    ("bgb_en.txt", "bgb", "BGB (English)", uuid.UUID("11111111-1111-4111-8111-111111110002")),
    ("bdsg_de.txt", "bdsg", "BDSG (German)", uuid.UUID("11111111-1111-4111-8111-111111110003")),
    ("eu_ai_act_en.txt", "eu_ai_act", "EU AI Act (English)", uuid.UUID("11111111-1111-4111-8111-111111110004")),
]


async def ingest_file(
    db: AsyncSession,
    path: Path,
    source: str,
    title: str,
    document_id: uuid.UUID,
    *,
    force: bool = False,
) -> int:
    if not path.is_file():
        print(f"  [SKIP] missing {path}")
        return 0

    raw = path.read_text(encoding="utf-8", errors="replace")
    structured = chunk_law_text(raw, source=source, title=title)
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
            "file": path.name,
            **item.get("metadata", {}),
        }
        contents.append(content)
        metas.append(meta)
        if settings.contextual_retrieval_enabled:
            embed_inputs.append(build_embedding_text(content, meta))
        else:
            embed_inputs.append(content)

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
    await db.commit()
    print(f"  [OK] {path.name}: {len(contents)} chunks (structured={bool(structured)})")
    return len(contents)


async def main(force: bool = False, graph_only: bool = False) -> None:
    from services.law_graph import rebuild_law_graph

    if graph_only:
        async with async_session_factory() as db:
            print(f"Citation graph rebuilt: {await rebuild_law_graph(db)}")
        return
    root = settings.law_corpus_path
    print(f"Ingesting law corpus from {root} (force={force})")
    total = 0
    missing = [filename for filename, *_ in LAW_FILES if not (root / filename).is_file()]
    if len(missing) == len(LAW_FILES):
        # Nothing to ingest would otherwise end with "Done. Total chunks: 0" and exit cleanly.
        raise SystemExit(f"No law files in {root}. Run: make download-law")
    async with async_session_factory() as db:
        for filename, source, title, doc_id in LAW_FILES:
            total += await ingest_file(db, root / filename, source, title, doc_id, force=force)
        await db.execute(
            text(
                """
                CREATE INDEX IF NOT EXISTS idx_document_chunks_embedding_hnsw
                ON document_chunks USING hnsw (embedding vector_cosine_ops)
                """
            )
        )
        await db.commit()
        # The graph is read from the provisions just ingested (D-016).
        print(f"Citation graph rebuilt: {await rebuild_law_graph(db)}")
    print(f"Done. Total chunks: {total}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Ingest GDPR/BGB law corpus")
    parser.add_argument("--force", action="store_true", help="Re-ingest even if corpus exists")
    parser.add_argument("--graph-only", action="store_true", help="Rebuild the citation graph from the ingested corpus")
    args = parser.parse_args()
    asyncio.run(main(force=args.force, graph_only=args.graph_only))

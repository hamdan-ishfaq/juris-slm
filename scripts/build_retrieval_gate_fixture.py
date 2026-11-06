#!/usr/bin/env python3
"""Rebuild the CI retrieval fixture from the ingested GDPR chunks. Needs the ML image and the database.

Run after any change to law chunking or embeddings, then reset the floor in eval/baseline.json:
  docker compose run --rm --no-deps -T -v "$PWD/eval:/app/eval" api \
    python /app/scripts/build_retrieval_gate_fixture.py
"""
from __future__ import annotations

import asyncio
import json
from pathlib import Path

import numpy as np
from sqlalchemy import text

from db import async_session_factory
from services.embeddings import embed_texts

EVAL = Path("/app/eval")
OUT = EVAL / "fixtures" / "retrieval_gate"


async def main() -> None:
    async with async_session_factory() as db:
        rows = (
            await db.execute(
                text(
                    "SELECT content, embedding::text AS vector FROM document_chunks "
                    "WHERE metadata->>'source' = 'gdpr' ORDER BY chunk_index"
                )
            )
        ).mappings().all()
    questions = [
        json.loads(line)
        for line in (EVAL / "golden" / "law_qa.jsonl").read_text().splitlines()
        if '"id": "gdpr-' in line
    ]
    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / "chunks.jsonl").write_text("".join(json.dumps({"content": r["content"]}) + "\n" for r in rows))
    (OUT / "queries.jsonl").write_text(
        "".join(
            json.dumps({"id": q["id"], "question": q["question"], "gold": q["gold_chunk_substrings"]}) + "\n"
            for q in questions
        )
    )
    np.savez_compressed(
        OUT / "vectors.npz",
        chunks=np.array([json.loads(r["vector"]) for r in rows], dtype=np.float16),
        queries=np.asarray(embed_texts([q["question"] for q in questions]), dtype=np.float16),
    )
    print(f"{len(rows)} chunks, {len(questions)} queries written to {OUT}")


if __name__ == "__main__":
    asyncio.run(main())

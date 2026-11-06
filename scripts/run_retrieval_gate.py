#!/usr/bin/env python3
"""PR gate: run the product's search code on committed GDPR chunks and vectors, with no models.

Fails when hit rate or keyword-leg coverage falls below the floors in eval/baseline.json. Covers search
and fusion only: embeddings are pre-computed and the reranker needs a model, so those are benchmarked
by `make bench`. Expects DATABASE_URL to point at a migrated, otherwise empty database.
"""
from __future__ import annotations

import argparse
import asyncio
import json
import sys
import uuid
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend" / "src"))
sys.path.insert(0, str(ROOT / "scripts"))

from db import async_session_factory  # noqa: E402
from eval_common import load_baseline, load_jsonl, save_report, substring_hit  # noqa: E402
from services.vector_store import (  # noqa: E402
    delete_by_document_id,
    hybrid_search,
    insert_chunk,
    search_fts,
)

FIXTURE = ROOT / "eval" / "fixtures" / "retrieval_gate"
DOCUMENT_ID = uuid.UUID("9c1f7a52-0a7e-4b19-9a33-5c2f8e6d1b01")
TOP_K = 5
ACCESS = {"include_law_corpus": True, "user_role": "owner"}


async def measure() -> dict:
    chunks = load_jsonl(FIXTURE / "chunks.jsonl")
    queries = load_jsonl(FIXTURE / "queries.jsonl")
    vectors = np.load(FIXTURE / "vectors.npz")
    misses: list[str] = []
    keyword_rows = 0
    async with async_session_factory() as db:
        await delete_by_document_id(db, DOCUMENT_ID)
        for index, (chunk, vector) in enumerate(zip(chunks, vectors["chunks"])):
            await insert_chunk(
                db,
                document_id=DOCUMENT_ID,
                chunk_index=index,
                content=chunk["content"],
                embedding=vector.astype(np.float32),
                metadata={"source": "gdpr", "kind": "law", "title": "GDPR"},
            )
        await db.commit()
        for query, vector in zip(queries, vectors["queries"]):
            hits = await hybrid_search(db, query["question"], vector.astype(np.float32), top_k=TOP_K, **ACCESS)
            if not substring_hit(" ".join(h["content"] for h in hits), query["gold"]):
                misses.append(query["id"])
            keyword_rows += bool(await search_fts(db, query["question"], top_k=TOP_K, **ACCESS))
    return {
        "chunks": len(chunks),
        "queries": len(queries),
        "top_k": TOP_K,
        "hit_rate": 1 - len(misses) / len(queries),
        "keyword_nonempty_rate": keyword_rows / len(queries),
        "miss_ids": misses,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--report", type=Path, default=None)
    args = parser.parse_args()
    report = asyncio.run(measure())
    print(json.dumps(report, indent=1))
    if args.report:
        save_report(args.report, report)
    floors = load_baseline()["retrieval_gate"]
    failures = [
        f"{name} {report[name]:.3f} is below the floor {floors[name + '_min']}"
        for name in ("hit_rate", "keyword_nonempty_rate")
        if report[name] < floors[name + "_min"]
    ]
    for failure in failures:
        print(f"FAIL: {failure}")
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())

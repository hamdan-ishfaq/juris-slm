"""H1: how often does the product keyword leg return nothing on the law golden questions?

Read-only. Copy into the API container, then feed it eval/golden/law_qa.jsonl on stdin.
Output is JSON with per-question counts from the real search_fts, on raw and expanded queries.
"""
import asyncio
import json
import sys

from sqlalchemy import text

from db import async_session_factory
from services.query_enhance import expand_legal_query
from services.vector_store import search_fts

QUESTIONS = json.loads(sys.argv[1]) if len(sys.argv) > 1 else None


async def main(questions: list[dict]) -> dict:
    rows = []
    async with async_session_factory() as db:
        for q in questions:
            raw = q["question"]
            expanded = expand_legal_query(raw)
            kwargs = {"top_k": 40, "include_law_corpus": True, "user_role": "owner"}
            raw_hits = await search_fts(db, raw, **kwargs)
            expanded_hits = await search_fts(db, expanded, **kwargs)
            # Same terms with OR instead of AND, to show what the AND requirement costs.
            or_query = await db.execute(
                text(
                    "SELECT count(*) FROM document_chunks WHERE content_tsv @@ "
                    "replace(plainto_tsquery('simple', :q)::text, '&', '|')::tsquery"
                ),
                {"q": expanded},
            )
            rows.append(
                {
                    "id": q["id"],
                    "raw": len(raw_hits),
                    "expanded": len(expanded_hits),
                    "or_matches": or_query.scalar_one(),
                    "was_expanded": expanded != raw,
                }
            )
    n = len(rows)
    return {
        "questions": n,
        "raw_empty": sum(r["raw"] == 0 for r in rows),
        "expanded_empty": sum(r["expanded"] == 0 for r in rows),
        "was_expanded": sum(r["was_expanded"] for r in rows),
        "or_empty": sum(r["or_matches"] == 0 for r in rows),
        "rows": rows,
    }


questions = [json.loads(line) for line in sys.stdin] if QUESTIONS is None else QUESTIONS
print(json.dumps(asyncio.run(main(questions)), indent=1))

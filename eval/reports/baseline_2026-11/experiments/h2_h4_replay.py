"""H2, H4, H6: replay real prompts to Ollama and record what the product never looks at.

Read-only. Builds each prompt with the product's own retrieval and prompt code, sends it with the
product's options, then records Ollama's counters and whether the extractive fallback would fire.
Feed eval/golden/law_qa.jsonl on stdin. Takes every 5th question.
"""
import asyncio
import json
import re
import sys
import time

import httpx

from config import settings
from db import async_session_factory
from services import rag
from services.llm_client import build_prompt


async def one(db, client, q: dict) -> dict:
    question = q["question"]
    started = time.perf_counter()
    ranked = await rag._retrieve_and_rank(
        db, question, accessible_ids=None, include_law=True, user_role="owner", doc_uuid=None, use_hyde=False
    )
    retrieve_s = time.perf_counter() - started
    context, sources = rag._format_context(ranked)
    prompt = build_prompt(context, question)
    response = await client.post(
        f"{settings.ollama_base_url.rstrip('/')}/api/generate",
        json={
            "model": settings.ollama_model,
            "prompt": prompt,
            "stream": False,
            "options": {"temperature": 0.1, "num_predict": 1024},
        },
    )
    response.raise_for_status()
    data = response.json()
    answer = (data.get("response") or "").strip()
    needs_article = bool(re.search(r"\bgdpr\b|article\s+\d", question, re.IGNORECASE))
    top = (ranked[0].get("content") or "") if ranked else ""
    reasons = {
        "refusal": rag._is_model_refusal(answer),
        "context_unused": not rag._answer_uses_context(answer, context, ranked_chunks=ranked),
        "no_article_cite": needs_article and rag._answer_lacks_article_cite(answer),
        "top_hit_mismatch": bool(top) and not rag._answer_matches_top_hit(answer, top),
    }
    return {
        "id": q["id"],
        "ranked": len(ranked),
        "blocks_in_context": len(sources),
        "context_chars": len(context),
        "prompt_chars": len(prompt),
        "retrieve_s": round(retrieve_s, 2),
        "done_reason": data.get("done_reason"),
        "prompt_eval_count": data.get("prompt_eval_count"),
        "eval_count": data.get("eval_count"),
        "load_s": round(data.get("load_duration", 0) / 1e9, 2),
        "prompt_eval_s": round(data.get("prompt_eval_duration", 0) / 1e9, 2),
        "eval_s": round(data.get("eval_duration", 0) / 1e9, 2),
        "total_s": round(data.get("total_duration", 0) / 1e9, 2),
        "tokens_per_s": round(data.get("eval_count", 0) / max(data.get("eval_duration", 1) / 1e9, 1e-9), 1),
        "answer_chars": len(answer),
        "has_phi_markers": "<|" in answer,
        "fallback_would_fire": any(reasons.values()),
        "fallback_reasons": [k for k, v in reasons.items() if v],
    }


async def main(questions: list[dict]) -> list[dict]:
    rows = []
    async with async_session_factory() as db, httpx.AsyncClient(timeout=1800) as client:
        for q in questions:
            row = await one(db, client, q)
            rows.append(row)
            print(json.dumps(row), file=sys.stderr, flush=True)
    return rows


all_questions = [json.loads(line) for line in sys.stdin]
print(json.dumps(asyncio.run(main(all_questions[::5])), indent=1))

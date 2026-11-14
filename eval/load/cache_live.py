#!/usr/bin/env python3
"""Live check of the semantic cache through the running API (D-022): ask questions, then rewordings, and time both.

The rewordings are the first ten of cache_pairs_v2.jsonl with an answer. Each original is asked once (filling the cache),
then its rewording; a hit is reported by the API's "cached" flag.

  python eval/load/cache_live.py
"""
from __future__ import annotations

import asyncio
import json
import statistics
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

import httpx

sys.path.insert(0, str(Path(__file__).resolve().parent))
from loadtest import API_BASE, OUT, ROOT, login_dev_master  # noqa: E402


async def chat(client: httpx.AsyncClient, token: str, question: str) -> dict:
    started = time.monotonic()
    final: dict = {}
    async with client.stream("POST", f"{API_BASE}/api/v1/chat/stream", headers={"Authorization": f"Bearer {token}"},
                             json={"message": question, "use_law_corpus": True}) as response:
        async for line in response.aiter_lines():
            if line.startswith("data: "):
                event = json.loads(line[6:])
                if event.get("type") == "final":
                    final = event
    return {"question": question, "s": round(time.monotonic() - started, 3), "cached": bool(final.get("cached"))}


async def main() -> int:
    golden = {json.loads(line)["id"]: json.loads(line)["question"]
              for line in (ROOT / "eval" / "golden" / "law_qa.jsonl").read_text().splitlines() if line.strip()}
    probes = [json.loads(line) for line in (ROOT / "eval" / "load" / "cache_pairs_v2.jsonl").read_text().splitlines()]
    pairs = [(golden[p["answer_id"]], p["probe"]) for p in probes if p["answer_id"]][:10]
    token = login_dev_master()["token"]
    rows = []
    async with httpx.AsyncClient(timeout=600) as client:
        for original, reworded in pairs:
            first = await chat(client, token, original)
            second = await chat(client, token, reworded)
            rows.append({"original": first, "reworded": second})
            print(first["s"], first["cached"], "->", second["s"], second["cached"], reworded, flush=True)
    hits = [r["reworded"]["s"] for r in rows if r["reworded"]["cached"]]
    misses = [r["original"]["s"] for r in rows if not r["original"]["cached"]]
    summary = {"pairs": len(rows), "rewordings_served_from_cache": len(hits),
               "hit_s_p50": round(statistics.median(hits), 3) if hits else None,
               "full_answer_s_p50": round(statistics.median(misses), 3) if misses else None}
    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / "semantic_cache_live.json").write_text(json.dumps(
        {"timestamp": datetime.now(timezone.utc).isoformat(), "summary": summary, "rows": rows}, indent=1) + "\n")
    print(summary)
    return 0


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))

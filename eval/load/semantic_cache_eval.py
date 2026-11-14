#!/usr/bin/env python3
"""Would a semantic answer cache serve wrong answers? (eval/load/PLAN.md step 5, D-022)

All 45 cached questions go into the cache. Each probe takes the nearest cached question by bge-m3 cosine similarity
among those that pass the guard; it's a hit if that similarity is at least tau. Scoring is strict:
  - a "miss" probe that hits anything is a wrong answer served;
  - a "hit" probe is right only if it hits its own cached question.

Two policies: similarity alone, and similarity plus a guard requiring the same provisions (article, paragraph, point)
and the same laws named. tau is chosen on a seeded half of the cached questions (with all their probes): the lowest value
with zero wrong hits on that half. It's then applied once to the other half.

Runs where bge-m3 is installed (the API image):
  docker cp eval/load jurisguard-api-1:/tmp/load
  docker exec -e PYTHONPATH=/app/src jurisguard-api-1 python /tmp/load/semantic_cache_eval.py /tmp/load/cache_pairs.jsonl
"""
from __future__ import annotations

import json
import math
import random
import re
import sys
import time
from pathlib import Path

SEED = 20261115
LAWS = {
    "gdpr": r"\b(gdpr|dsgvo)\b", "bdsg": r"\bbdsg\b", "bgb": r"\bbgb\b", "ai_act": r"\bai act\b",
}
PROVISION = re.compile(r"(?:art(?:icle)?s?\.?|§|section)\s*(\d+)((?:\(\d+\))?(?:\([a-z]\))?)(?:\s*-\s*(\d+))?", re.I)


def signature(question: str) -> tuple:
    """Provisions with their paragraph and point, and the laws named. Two questions must match exactly to share an answer."""
    q = question.lower()
    provisions = tuple(sorted(f"{m.group(1)}{m.group(2)}" + (f"-{m.group(3)}" if m.group(3) else "")
                              for m in PROVISION.finditer(q)))
    laws = tuple(sorted(name for name, pattern in LAWS.items() if re.search(pattern, q)))
    return provisions, laws


def wilson_upper(k: int, n: int) -> float:
    if not n:
        return 1.0
    p, z = k / n, 1.96
    centre = (p + z * z / (2 * n)) / (1 + z * z / n)
    half = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / (1 + z * z / n)
    return round(min(1.0, centre + half), 4)


def main() -> int:
    from services.embeddings import embed_texts

    pairs = [json.loads(line) for line in Path(sys.argv[1]).read_text().splitlines() if line.strip()]
    cached = {}
    for p in pairs:
        cached[p["id"]] = p["cached"]
    ids = sorted(cached)
    random.Random(SEED).shuffle(ids)
    dev_ids = set(ids[: len(ids) // 2])

    cache_ids = list(cached)
    cache_vecs = embed_texts([cached[i] for i in cache_ids])
    probe_vecs = embed_texts([p["probe"] for p in pairs])
    started = time.perf_counter()
    for p in pairs[:20]:
        embed_texts([p["probe"]])
    embed_ms = (time.perf_counter() - started) * 1000 / 20

    cache_sigs = [signature(cached[i]) for i in cache_ids]
    for p, vec in zip(pairs, probe_vecs):
        sims = cache_vecs @ vec
        sig = signature(p["probe"])
        best_any = int(sims.argmax())
        guarded = [k for k in range(len(cache_ids)) if cache_sigs[k] == sig]
        best_guarded = max(guarded, key=lambda k: sims[k]) if guarded else None
        p["any"] = (cache_ids[best_any], float(sims[best_any]))
        p["guarded"] = (cache_ids[best_guarded], float(sims[best_guarded])) if best_guarded is not None else (None, -1.0)
        p["split"] = "dev" if p["id"] in dev_ids else "test"

    def score(rows: list[dict], policy: str, tau: float) -> dict:
        hits_right = wrong = 0
        n_hit = sum(r["expect"] == "hit" for r in rows)
        n_miss = len(rows) - n_hit
        wrong_kinds: dict[str, int] = {}
        for r in rows:
            target, sim = r[policy]
            if sim < tau:
                continue
            if r["expect"] == "hit" and target == r["id"]:
                hits_right += 1
            elif r["expect"] == "miss" or target != r["id"]:
                wrong += 1
                wrong_kinds[r["kind"]] = wrong_kinds.get(r["kind"], 0) + 1
        return {"tau": round(tau, 4), "paraphrase_hits": hits_right, "paraphrases": n_hit,
                "paraphrase_hit_rate": round(hits_right / n_hit, 4) if n_hit else None,
                "wrong_answers": wrong, "probes": len(rows), "near_misses": n_miss,
                "wrong_rate_upper95": wilson_upper(wrong, len(rows)), "wrong_by_kind": wrong_kinds}

    dev = [r for r in pairs if r["split"] == "dev"]
    test = [r for r in pairs if r["split"] == "test"]
    report = {"seed": SEED, "dev_questions": len(dev_ids), "test_questions": len(ids) - len(dev_ids),
              "embed_ms_per_question_cpu": round(embed_ms, 1), "policies": {}}
    for policy in ("any", "guarded"):
        candidates = sorted({r[policy][1] for r in dev if r[policy][1] > 0} | {1.0001})
        # The lowest tau with zero wrong answers on dev: any wrong probe at or above it would count.
        tau = next(t for t in candidates if score(dev, policy, t)["wrong_answers"] == 0)
        report["policies"][policy] = {"dev": score(dev, policy, tau), "test": score(test, policy, tau)}
    report["closest_wrong_on_test"] = sorted(
        ({"probe": r["probe"], "cached": cached[r["guarded"][0]], "sim": round(r["guarded"][1], 4), "kind": r["kind"]}
         for r in test if r["guarded"][0] and (r["expect"] == "miss" or r["guarded"][0] != r["id"])),
        key=lambda x: -x["sim"])[:8]
    print(json.dumps(report, indent=1, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

#!/usr/bin/env python3
"""Paired comparison of the A-B-B-A latency passes: per question, mean of a model's two passes, then Qwen3 minus Mistral."""
import json
import random
import statistics
from pathlib import Path

HERE = Path(__file__).parent
passes = {p.stem: json.loads(p.read_text())["results"] for p in sorted(HERE.glob("pass*_*.json"))}
samples = {k: v["chat_ms"]["samples_s"] for k, v in passes.items()}
by_model = {"qwen3_8b": [], "mistral_7b": []}
for name, s in samples.items():
    by_model[name.split("_", 1)[1]].append(s)
assert all(len(x) == 50 for runs in by_model.values() for x in runs)
per_q = {m: [statistics.mean(r[i] for r in runs) for i in range(50)] for m, runs in by_model.items()}
diff = [q - m for q, m in zip(per_q["qwen3_8b"], per_q["mistral_7b"])]
rng = random.Random(20261114)
boot = sorted(statistics.mean(rng.choices(diff, k=50)) for _ in range(5000))


def pct(xs, p):
    xs = sorted(xs)
    k = (len(xs) - 1) * p
    lo, hi = int(k), min(int(k) + 1, len(xs) - 1)
    return xs[lo] + (xs[hi] - xs[lo]) * (k - lo)


out = {
    "questions": 50,
    "passes": {k: {"p50_s": round(statistics.median(v), 2), "p95_s": round(pct(v, 0.95), 2), "max_s": round(max(v), 2),
                   "generate_p50_ms": round(passes[k]["stages_ms"]["generate"]["p50"])} for k, v in samples.items()},
    "pooled": {m: {"p50_s": round(statistics.median(sum(r, [])), 2), "p95_s": round(pct(sum(r, []), 0.95), 2), "n": 100}
               for m, r in by_model.items()},
    "paired_mean_difference_qwen3_minus_mistral_s": round(statistics.mean(diff), 2),
    "paired_ci95_s": [round(boot[125], 2), round(boot[4875], 2)],
    "qwen3_faster_on": sum(d < 0 for d in diff),
}
(HERE / "summary.json").write_text(json.dumps(out, indent=1) + "\n")
print(json.dumps(out, indent=1))

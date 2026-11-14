# Answer time by model, same code, 50 questions, 2026-11-14

A review asked what made answers faster between Mistral 7B and Qwen3 8B. Checking it showed the earlier figures couldn't say:
`scripts/run_latency_bench.py` asked one GDPR question 10 times, and two Mistral runs four minutes apart on 2026-11-07, the
second doing more work, gave p50 13.6 s and 10.5 s. So this run changes only the model, on today's code.

## Setup

- Code at `1c5b928`, plus the harness change committed as `94f65fd` (asks each question once, keeps raw times).
- The 50 questions of `eval/golden/law_qa.jsonl`, each asked once per pass, with the pass's run number appended.
- Passes in the order Qwen3, Mistral, Mistral, Qwen3, so neither model always gets the cooler or warmer GPU.
- Before each pass, the API restarted with that model, one untimed warm-up question, and the answer cache cleared before
  and after the warm-up (0 keys left each time). Both models were 100% on the GPU (Ollama `/api/ps`).
- RTX 4050 6 GB laptop GPU, Ollama 0.40.15, `OLLAMA_NUM_PARALLEL=1`.

## Result (`summary.json`, from the raw times in each `pass*.json`)

| Pass | Model | p50 | p95 | Slowest | Generation p50 |
|---|---|---|---|---|---|
| 1 | Qwen3 8B | 9.0 s | 17.0 s | 22.0 s | 7.1 s |
| 2 | Mistral 7B | 7.7 s | 15.8 s | 17.9 s | 5.9 s |
| 3 | Mistral 7B | 7.7 s | 17.3 s | 22.7 s | 6.0 s |
| 4 | Qwen3 8B | 7.6 s | 16.6 s | 34.9 s | 5.3 s |

Pooled, n=100 runs per model: Qwen3 p50 8.5 s and p95 16.8 s; Mistral p50 7.7 s and p95 16.9 s.

Per question, each model's two passes averaged: Qwen3 minus Mistral is +0.53 s, 95% interval −0.62 to +1.75 s (bootstrap,
5,000 resamples). Qwen3 was faster on 15 of the 50 questions.

## What it means

- The model choice makes no measurable difference to answer time. Qwen3 was chosen for answer quality (D-010), and that
  stands; the latency improvement once attributed to it doesn't.
- The earlier "p50 9.1 s, p95 9.2 s" came from one question asked ten times, which gives nearly identical times. Across 50
  different questions the tail is about twice that: p95 16.8 s.
- The same model's median moved 1.4 s between its two passes, more than the gap between the models. Ten runs of one
  question couldn't have shown a difference smaller than that.
- Cold start (the first question after a restart) is a separate measure and wasn't re-run here.

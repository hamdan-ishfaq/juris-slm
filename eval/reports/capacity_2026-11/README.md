# Capacity, admission control and caching, 2026-11-14 to 15 (D-020 to D-022)

A system-design review graded this part B: sound for its stated load, but "what breaks at ten times the load" in
`docs/DESIGN.md` was estimated, nothing ordered work on the one GPU, and the cache had a staleness bug. The plan and
adoption rules were committed before any code (`eval/load/PLAN.md`). Every run, including the failed ones, is in this
folder.

**Setup:** RTX 4050 6 GB laptop, Qwen3 8B 100% on the GPU (Ollama `/api/ps` before every level), one Ollama slot unless
stated. `eval/load/loadtest.py` runs N simulated users through `/api/v1/chat/stream`, the endpoint the UI uses. Every
level asks the same 24 questions (`gdpr-001` to `gdpr-024` of `eval/golden/law_qa.jsonl`), with a run tag so the cache
never answers. Times are measured by the client.

## 1. Capacity of the unchanged system (`baseline.md`)

| Users | Answers per minute | First token p50 / p95 | Full answer p50 / p95 |
|---|---|---|---|
| 1 | 6.6 | 2.4 / 4.0 s | 9.1 / 12.8 s |
| 2 | 7.8 | 6.7 / 15.8 s | 13.5 / 23.8 s |
| 4 | 8.0 | 19.7 / 38.9 s | 25.6 / 46.8 s |
| 8 | 8.7 | 40.9 / 57.2 s | 47.2 / 64.2 s |
| 12 | 8.0 | 60.0 / 98.2 s | 66.5 / 102.9 s |

- **Throughput:** the GPU saturates at about 8.5 answers a minute, roughly 500 an hour. More users only add waiting.
  Generation is about 6.5 s of a 9 s answer; the CPU stages (rerank 0.6 s, law graph 0.9 s, relevance check 0.5 s)
  overlap with another user's generation, which is why throughput rises a little past one user.
- **Single user:** the first text appears 2.4 s after sending (p50), and the full checked answer at 9.1 s.
- **Failed first attempt:** `first_attempt_mixed_questions.md`. It gave each level a different slice of questions, and
  one slice held the out-of-scope questions, which are refused without an LLM call. That level looked twice as fast.
  Rerun with the same questions at every level.

## 2. Two parallel slots (D-020): not adopted (`p1_current.md`, `p2.md`)

Rule: Qwen3 stays 100% on the GPU, answers per minute at 4 users rise at least 15%, and single-user p50 rises at most
10%. Compared with one slot on the same code:

| Users | One slot: per min, full answer p50 | Two slots: per min, full answer p50 |
|---|---|---|
| 1 | 7.1, 8.6 s | 4.1, 14.7 s |
| 2 | 7.9, 13.8 s | 5.6, 19.6 s |
| 4 | 8.8, 25.0 s | 6.0, 36.3 s |

- **Fit:** both slots fitted fully on the GPU (6.19 GB, KV cache 1.15 GB). It was still slower at every level.
- **Where the time went** (`ollama_speed_one_vs_two_slots.txt`): prompt reading fell from 1,593 to 206 tokens per
  second, and generation from 32.9 to 22.2. RAG prompts are about 1,300 tokens, so prompt reading dominates. The reason
  for the slowdown wasn't investigated further.
- **Failed attempt:** the first try loaded the model with a bare warm-up request, without the app's `num_gpu` and
  `use_mmap` options. It read as 70% on the GPU, an artifact, and the q8 KV retry after it never started. Rerun with
  the app's options.
- **Unmeasured level:** two slots at 8 users got 401 on every request. The client's login expired during the long run.
  It now logs in per level. That level wasn't needed for the decision.

## 3. Admission control and priority (D-021) (`overload_*.md`, `priority_*.json`)

All runs at 12 users on the same 24 questions:

| Gate | Answered | End to end p50 / p95 | First thing the user is told, p50 / p95 |
|---|---|---|---|
| None | 24 / 24 | 66.5 / 102.9 s | 60.0 / 98.2 s (first token) |
| Limit 6, 429, client retries 3 times | 14 / 24 | 32.1 / 79.5 s | 4.6 / 42.8 s |
| Limit 6, 429, client retries for 180 s | 24 / 24 | 46.5 / 168.7 s | 26.1 / 58.5 s |
| **Limit 16, queue position first, Ollama's FIFO kept** | **24 / 24** | **65.3 / 98.9 s** | **0.12 / 0.57 s** |

- **Retry gates:** rejecting early and retrying lost arrival order and doubled the tail. With three retries, 10
  questions were never answered.
- **Adopted gate:** keeps the order and the latency of no gate, and tells every user their place in half a second.
- **Background lane:** gap analysis waits before each model call while a user's question is in the system. A question
  asked during a gap analysis got its first token at a median of 3.6 s with the gate and 3.8 s without (5 rounds each,
  worst case 4.2 s against 6.6 s). The gap analysis makes short calls, so the gain is small.

## 4. Semantic cache (D-022) (`semantic_cache.json`, `semantic_cache_v2.json`, `semantic_cache_live.json`)

Rule: zero wrong answers on held-out near misses, and at least 30% of rewordings served. The pairs were written by hand
before scoring (`eval/load/cache_pairs*.jsonl`): rewordings, and near misses that use another article, law or point,
or ask the same provision something else.

| Set | Policy | Rewordings served | Wrong answers |
|---|---|---|---|
| First, held-out half (tau 0.9531 from its dev half) | similarity alone | 27 / 46 | 4 (all another point of Article 6(1)) |
| First, held-out half | similarity + same provisions and laws | 27 / 46 | 1 |
| Second, fresh, all held out, tau unchanged | similarity + same provisions and laws | 27 / 45 | 0 of 103 near misses (upper bound 3.6%) |

- **The first set's one wrong hit:** a near miss that asks exactly what another cached question asks ("When is
  legitimate interest a lawful basis under Article 6(1)(f)?"). It fails the rule as written, and stays recorded as a
  fail. The second set names the intended answer for every probe, and it decided.
- **Live, through the API:** 7 of 10 rewordings came from the cache, at a median of 0.10 s against 7.7 s for a full
  answer.
- **Caveat:** every pair was written by the developer, so the hit rate for real users is unknown.

## 5. Cache correctness fixes

- **Corpus version:** the key now includes it, and ingest bumps it. Before, a re-ingested law kept serving older
  answers for up to the one-hour TTL.
- **Organisation:** the key now includes it, because law answers can draw on regulations one organisation uploaded.
  Before, such an answer could be served to another organisation.

Both are covered by unit tests in `backend/tests/test_query_cache.py`.

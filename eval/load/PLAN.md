# Phase 12: capacity, admission control and caching

Written 2026-11-14, before any code or measurement. A review graded the system design B: sound for its stated load,
but the load figures in `docs/DESIGN.md` are estimates, nothing limits or orders work on the one GPU, and the cache has
a staleness bug. This phase measures first and changes things only where a measurement says so.

Constraints, unchanged: one RTX 4050 6 GB laptop, Qwen3 8B 100% on the GPU, no paid service, one heavy GPU job at a time.

## What the sources say, and what we take from them

- **Measure streaming milestones, not request time.** Load tools time a request to its last byte unless told otherwise;
  for an LLM, time to first token and total time must be recorded separately, and a small rise in concurrency changes
  both sharply ([Pan, 2026](https://tianpan.co/blog/2026-03-19-load-testing-llm-applications);
  [LoadForge](https://loadforge.com/guides/ai-llm/load-testing-llm-streaming-responses)). k6 needs an extension for SSE,
  and Locust needs custom events or a plugin ([locust-sse](https://awesome.ecosyste.ms/projects/github.com%2Faleph-alpha%2Flocust-sse)).
  **Taken:** a small asyncio client in `eval/load/`. It reads our own SSE events and records first token, total time
  and errors per request, with no new dependency.
- **Ollama queues FIFO and rejects late.** `OLLAMA_NUM_PARALLEL` defaults to 1, `OLLAMA_MAX_QUEUE` to 512, a full queue
  returns 503, and memory grows with parallel × context ([Ollama FAQ](https://docs.ollama.com/faq)). So today a 10th
  user waits behind nine others with no signal, and nothing puts a chat question ahead of a gap analysis.
- **Reject early, with a time to retry.** A bounded queue, then 429 with `Retry-After`, beats a request that waits and
  times out. Interactive and batch work belong in separate lanes, with batch shed first
  ([Spheron](https://www.spheron.network/blog/llm-inference-overload-queuing-load-shedding-and-admission-c/);
  [Hivenet router docs](https://routerdocs.hivenet.com/routing/admission-control);
  [Pan, backpressure](https://tianpan.co/blog/2026-04-16-backpressure-llm-pipelines-queue-theory)).
- **Semantic caches serve confident wrong answers.** A static similarity threshold is unreliable. vCache (arXiv
  [2502.03771](https://arxiv.org/abs/2502.03771)) learns a threshold per cached prompt to meet a set error rate. A banking
  FAQ study saw 99% false positives at a 0.7 threshold and 27% at 0.9
  ([InfoQ](https://www.infoq.com/articles/reducing-false-positives-retrieval-augmented-generation)). In law, "Article 6"
  and "Article 9" questions are close in embedding space and have different answers. **Taken:** a semantic hit also
  needs the same cited provisions and law, and a cache is adopted only if it serves no wrong answers on near-miss pairs.

## Steps, in order

### 1. Cache key includes the corpus version (bug fix)

`query_cache._cache_key` hashes the question and flags only, so after a law is re-ingested, an old answer is served
until the one-hour TTL ends. Fix: a Redis counter `juris:corpus_version`, read into the key and bumped whenever a corpus
source finishes ingesting (worker task and the host ingest script). Old keys then expire unused. Test first: an answer
cached, the version bumped, the next read a miss.

### 2. Baseline load test, unchanged system

`eval/load/loadtest.py` runs a closed-loop sweep at 1, 2, 4 and 8 concurrent users. Each user asks distinct law questions
from `eval/golden/law_qa.jsonl`, with a run tag so the cache never serves them, through `/api/v1/chat/stream`, 24
answers per level. Before each level, one warm-up question is asked and Qwen3 is confirmed 100% on the GPU.

Recorded per level: time to first token and total time (p50, p95), answers per minute, errors by status, and seconds
spent waiting (first token minus the single-user first token). Raw per-request rows are saved. This replaces the
"about 7 answers a minute" estimate.

### 3. Two parallel slots (D-020)

Ollama with `OLLAMA_NUM_PARALLEL=2`, context unchanged (4,096 per slot). The KV cache grows by about 0.6 GB (estimate:
36 layers × 8 KV heads × 128 × 2 × 2 bytes × 4,096). If the model no longer fits fully on the GPU, retry once with
`OLLAMA_KV_CACHE_TYPE=q8_0`. If it still doesn't fit, record the failure and stop this step.

Adopt only if all hold, on the same sweep:
- Qwen3 stays 100% on the GPU;
- answers per minute at 4 users rise by at least 15%;
- single-user p50 total time doesn't rise by more than 10%.

### 4. Admission control and priority (D-021)

A gate shared through Redis, because chat runs in the API and gap analysis in the Celery worker:

- **Interactive lane:** chat and document questions. If more than `GPU_QUEUE_LIMIT` interactive requests are running or
  waiting, the API answers 429 immediately. `Retry-After` is the wait estimated from the queue and the measured mean
  answer time, and the UI shows "Busy, retrying in N s" and retries with jitter.
- **Background lane:** gap analysis and graph extraction. Before each model call, a background job waits while any
  interactive request is waiting or running, so a chat question never queues behind it in Ollama.
- **Safety:** counters carry a TTL, so a crashed request can't hold a slot. If Redis is down, the gate fails open with a
  warning, as the cache does.

Measured with the step-2 tool:
- at 12 users, against the step-2 system: rejected requests answered fast instead of timing out, and p95 for accepted
  requests;
- a chat question asked during a gap analysis: its first-token time with and without the gate.

Adopt if accepted p95 at overload falls and the chat-during-gap-analysis wait falls; publish the numbers either way.

### 5. Semantic cache, as an experiment (D-022)

A pair set written before any scoring, in `eval/load/cache_pairs.jsonl`:
- **Paraphrase pairs (should hit):** two wordings of each of the 50 law questions, written by hand.
- **Near-miss pairs (must miss):** the same wording with a different article, paragraph or law, 100 or more pairs.

Policy: a hit needs all of
- cosine similarity of the bge-m3 embeddings at or above τ;
- the same cited provisions and law, extracted by the existing citation parser;
- the same corpus version and flags.

τ is chosen on a seeded half of the pairs and scored once on the other half.

Adopt only if the held-out near-miss pairs get zero wrong hits, with the Wilson upper bound reported, and paraphrase
hits are at least 30%. Also report the time a hit takes against a full answer. Otherwise publish it as a negative result,
and the exact cache stays.

### 6. Write-up

- `docs/DESIGN.md`: the estimates in "What breaks at ten times the load" become measured figures, and a scale-out
  section is added. Beyond one laptop: vLLM with continuous batching on a larger GPU, one shared embedding service
  instead of a copy per process, API replicas behind a load balancer, read replicas, per-tenant quotas. Labelled as not
  measured.
- README and handoff §26 get only the measured numbers. D-020 to D-022 are logged whatever the result.

## Not doing

- Distributed tracing across machines, autoscaling, Kubernetes: there's one machine.
- Prompt or KV prefix caching across users. Ollama doesn't expose it in a way we can measure.
- A cost-per-answer figure, which the owner decided against.

### Amendment, 2026-11-15, before the second scoring

The first pair set (`cache_pairs.jsonl`) was scored once. With the guard and tau = 0.9531 from its dev half, the held-out
half had 1 wrong hit: "When is legitimate interest a lawful basis under Article 6(1)(f)?", written as a near miss of the
Article 6(1)(b) question, landed on the cached Article 6(1)(f) question, which asks the same thing. Under the rule as
written, that is a fail, and it stays recorded as one.

A second, fresh set decides adoption: `cache_pairs_v2.jsonl`, 148 new probes, none reused. Each names the cached
question that should answer it, or none. The rule is unchanged otherwise:
- tau stays 0.9531, with no re-tuning;
- guarded policy;
- zero wrong hits over all 103 near misses, with the Wilson upper bound reported;
- at least 30% of the 45 rewordings hit their own question.

Scored once.

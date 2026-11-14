# Design

How JurisGuard answers a question, what it was built for, what was measured, and where it breaks. Decisions are in
[`DECISIONS.md`](DECISIONS.md); every number here comes from a report under `eval/reports/`.

## What it is built for

- **One organisation, on its own hardware.** The reference machine is a laptop: RTX 4050 with 6 GB, 12 GB of RAM for WSL,
  8 CPU cores. Everything runs locally; a packet capture showed no connection to a public address
  (`eval/reports/security_2026-11/`).
- **A handful of users at a time.** One LLM fits the GPU, and Ollama serves one request at a time
  (`OLLAMA_NUM_PARALLEL=1`, D-001, D-003, D-020). Measured, it saturates at about 8.5 answers a minute, roughly 500 an
  hour (`eval/reports/capacity_2026-11/`).
- **Statutes plus uploaded contracts.** Four laws (GDPR, BDSG, BGB, AI Act; 4,129 chunks) and each organisation's documents.

## A question, step by step

Stage times from Phase 5, Qwen3 8B 100% on the GPU, one GDPR question asked 10 times
(`eval/reports/llm_latency_2026-11/latency_stages_qwen3_8b.json`). They show where the time goes; for the total across
different questions see the line under the table.

| Stage | p50 | p95 | Where |
|---|---|---|---|
| Injection guard | <0.1 ms | 0.1 ms | `services/security.py` |
| Answer cache | (a hit returns in 37 ms) | | `services/query_cache.py` |
| Embed the question (CPU) | 83 ms | 122 ms | `services/embeddings.py` |
| Search: vector, plus keywords when a provision is cited (D-002) | 25 ms | 31 ms | `services/vector_store.py` |
| Choosing documents: filename rule, then nearest descriptions (D-005, D-007, D-015) | in retrieve | | `services/rag.py` |
| Rerank (CPU, law and cited questions only, D-004, D-006) | 571 ms | 665 ms | `services/reranker.py` |
| Retrieve, all of the above | 684 ms | 775 ms | |
| Citation graph, for law questions (D-016, measured in Phase 7) | 730 ms average | | `services/law_graph.py` |
| Generate (GPU), streamed as a draft (D-009) | 7.7 s | 7.9 s | `services/llm_client.py` |
| Relevance check (D-014) | 663 ms | 690 ms | `services/rag.py` |
| Citation check | 0.6 ms | 0.8 ms | `services/citation_verifier.py` |
| **Total, before the graph step, one question repeated** | **9.1 s** | **9.2 s** | |

Across 50 different law questions (n=100, 2026-11-14, graph step included) the total is p50 8.5 s and p95 16.8 s: answer
length varies with the question, and a repeated question hides that
(`eval/reports/llm_latency_2026-11/model_ab_2026-11-14/`).

The first streamed token arrives about 0.4 s after retrieval. Generation is 85% of the time; everything else runs on the
CPU so the LLM can have the whole GPU (D-001).

## Failure modes that were tested

| Failure | What happens | Where it's tested |
|---|---|---|
| Ollama down or failing mid-request | A gap-analysis item is retried once, then marked "not checked". Chat returns an error; no test covers that case | `test_contract_review.py` |
| Model reply that isn't the schema | Retried once, then "not checked" | `test_contract_review.py` |
| Quote not in the contract | Asked once more, then "not verified" | `test_contract_review.py` |
| Gap-analysis call budget spent | Remaining items "not checked", no further calls | `test_contract_review.py` |
| A model refusal or an answer unrelated to the retrieved text | Replaced by quoted text; ContractNLI showed a fluent wrong answer on the right topic still passes | `test_answer_mode.py`, `eval/reports/grounding_2026-11/` |
| An answer citing an article not in the retrieved sources | A disclaimer is added to the answer | `test_citation_verifier.py` |
| Instructions hidden in an uploaded document | Treated as data; 1 of 120 BIPIA attacks still followed | `eval/reports/security_2026-11/` |
| Another organisation's documents or corpus | Never retrieved; 404 on direct access | isolation tests, E2E |
| MCP request without a valid token | 401 | `test_mcp_server.py`, live check |
| Unsafe production settings | Startup refused | `test_config_security.py` |

## What breaks at ten times the load

Measured on the reference laptop, the same 24 questions at every level (`eval/reports/capacity_2026-11/`):

| Users at once | Answers per minute | First token p50 | Full answer p95 |
|---|---|---|---|
| 1 | 6.6 | 2.4 s | 12.8 s |
| 4 | 8.0 | 19.7 s | 46.8 s |
| 8 | 8.7 | 40.9 s | 64.2 s |
| 12 | 8.0 | 60.0 s | 102.9 s |

- **Concurrency is the first limit.** Past two users, every extra user only adds waiting. The gate (D-021) keeps
  Ollama's first-in, first-out order, tells each user their place within 0.6 s, refuses past 16 in the system (about
  2 minutes of queue), and makes gap analysis, graph extraction and ingest wait while a user's question is in the
  system. A second Ollama slot on the same GPU was slower at every load (D-020).
- **Repeats and rewordings skip the GPU.** An exact repeat comes from the cache in 37 ms. A rewording with the same
  cited provisions takes about 0.1 s (D-022): 27 of 45 test rewordings were served, with no wrong answer on 103 near
  misses.
- **RAM.** The API and the worker each hold the embedding and reranking models in RAM (about 2.2 GB each); the MCP server
  a third copy. More workers multiply that. Embedding in one service the others call would share one copy.
- **Corpus size.** Vector search stays fast with the HNSW index: 25 ms over the law corpus, and LegalBench-RAG's 182,914
  chunks were searched without trouble. Choosing documents by filename broke at 714 documents before D-007 tightened it;
  far larger collections would need it measured again.
- **Ingest.** Embedding on the CPU takes about 0.5 s a chunk; a 1,000-page upload would take tens of minutes. The worker
  queue absorbs it, but nothing is searchable until it finishes.

## Beyond one laptop (not measured)

What would change, in order, if the load grew past what one 6 GB GPU serves:

1. **A server with continuous batching** (vLLM or llama.cpp server on a larger GPU) instead of Ollama. It runs many
   requests in one batch instead of one after another. That is the step that raises answers per minute; more slots on
   this GPU didn't (D-020).
2. **One embedding and reranking service** that the API, worker and MCP server call, instead of a copy in each process.
3. **Several API replicas behind a load balancer.** The gate and the cache already live in Redis, so replicas share
   them. Postgres gets a read replica for search.
4. **Per-organisation quotas** on top of the global gate, so one busy organisation can't fill the queue for the rest.

## Rolling it out

1. Install on the target machine with `.env.airgap.example` (`ENVIRONMENT=production`); the settings check refuses weak
   secrets, open registration, a cloud API key or a tracing endpoint off the local network.
2. `make check-llm-gpu` must pass: the LLM entirely on the GPU.
3. Ingest the law corpus, which also builds the citation graph, and run `make e2e` and `make eval-logical` as a smoke test.
4. Run `GET /api/v1/audit/verify` after every upgrade.
5. Optional: `make mcp-up` with a token from `scripts/mcp_token.py` for assistants.

Measured results, defects and their reports are listed in the README.

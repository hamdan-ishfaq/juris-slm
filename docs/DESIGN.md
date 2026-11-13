# Design

How JurisGuard answers a question, what it was built for, what was measured, and where it breaks. Decisions are in
[`DECISIONS.md`](DECISIONS.md); every number here comes from a report under `eval/reports/`.

## What it is built for

- **One organisation, on its own hardware.** The reference machine is a laptop: RTX 4050 with 6 GB, 12 GB of RAM for WSL,
  8 CPU cores. Everything runs locally; a packet capture showed no connection to a public address
  (`eval/reports/security_2026-11/`).
- **A handful of users at a time.** One LLM fits the GPU, and Ollama serves one request at a time
  (`OLLAMA_NUM_PARALLEL=1`, D-001, D-003). Two people asking at once means the second waits for the first.
- **Statutes plus uploaded contracts.** Four laws (GDPR, BDSG, BGB, AI Act; 4,129 chunks) and each organisation's documents.

## A question, step by step

Measured on the reference machine with Qwen3 8B 100% on the GPU, 10 law questions, Phase 5
(`eval/reports/llm_latency_2026-11/latency_stages_qwen3_8b.json`):

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
| **Total, before the graph step** | **9.1 s** | **9.2 s** | |

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

Estimates from the measurements above, not load tests:

- **Concurrency.** Generation takes about 8 s and the GPU serves one request at a time, so roughly 7 answers a minute at
  most. Ten users asking at once would wait up to about 80 s. This is the first limit to hit. The fix is a bigger GPU or a
  second one, with `OLLAMA_NUM_PARALLEL` raised to match.
- **RAM.** The API and the worker each hold the embedding and reranking models in RAM (about 2.2 GB each); the MCP server
  a third copy. More workers multiply that. Embedding in one service the others call would share one copy.
- **Corpus size.** Vector search stays fast with the HNSW index: 25 ms over the law corpus, and LegalBench-RAG's 182,914
  chunks were searched without trouble. Choosing documents by filename broke at 714 documents before D-007 tightened it;
  far larger collections would need it measured again.
- **Ingest.** Embedding on the CPU takes about 0.5 s a chunk; a 1,000-page upload would take tens of minutes. The worker
  queue absorbs it, but nothing is searchable until it finishes.

## Rolling it out

1. Install on the target machine with `.env.airgap.example` (`ENVIRONMENT=production`); the settings check refuses weak
   secrets, open registration, a cloud API key or a tracing endpoint off the local network.
2. `make check-llm-gpu` must pass: the LLM entirely on the GPU.
3. Ingest the law corpus, which also builds the citation graph, and run `make e2e` and `make eval-logical` as a smoke test.
4. Run `GET /api/v1/audit/verify` after every upgrade.
5. Optional: `make mcp-up` with a token from `scripts/mcp_token.py` for assistants.

Measured results, defects and their reports are listed in the README.

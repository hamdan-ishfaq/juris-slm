# Decisions

## D-001: LLM takes the GPU, embedding and reranking run on the CPU
**Date:** 2026-11-06 · **Status:** Accepted

**Context:** The target machine has a 6 GB GPU (RTX 4050) and 16 GB of RAM, 12 GB of it given to WSL. The LLM
must run fully on the GPU. Ollama's automatic split put 11% of Mistral-7B on the CPU, and the API and worker
held 5,054 MiB of GPU memory between them for bge-m3 and the reranker.

| Option | Good | Bad | Effort |
|---|---|---|---|
| LLM on GPU, embed and rerank on CPU | Mistral at 38 tokens/s; about 0.5 s added per question | Bulk ingest about 0.5 s per chunk; 2.2 GiB RAM per process | Small |
| Embed and rerank on GPU, smaller LLM | Fast ingest and search | About 1 GB of GPU memory left for an LLM | Medium |
| Swap models per stage | Every stage on GPU | A model reload on each question (a Mistral load took 2.3-13 s) | Large |

Measured with Mistral-7B q4_K_M, `num_ctx` 4096, and a 1,820-token prompt:

| Setting | GPU share | GPU memory | Generation |
|---|---|---|---|
| Ollama automatic | 89% | 4,127 MiB | 19.8 tokens/s |
| `num_gpu` 99 | 100% | 4,837 MiB | 38.1 tokens/s |

On the CPU, bge-m3 took 88 ms per query at best and the reranker 385 ms for 20 pairs.

**Decision:** Run the LLM with `num_gpu` 99 on the GPU, and embedding and reranking on the CPU. Ollama keeps one
model loaded at a time (`OLLAMA_MAX_LOADED_MODELS=1`).

**Why:** Generation is by far the slowest stage, and full offload doubled its speed. The CPU stages add under a
second per question.

**Why not the others:** Nothing useful fits in the 1 GB left beside embed and rerank. Swapping costs more time
per question than it saves.

**Consequences:** Forcing `num_gpu` skips Ollama's safety estimate, so nothing else can hold GPU memory while
the LLM runs. `make check-llm-gpu` fails if any of the LLM is off the GPU. Bulk ingest and benchmarks with no LLM
loaded can use `docker-compose.gpu.yml`, which must not stay up beside the LLM. The API and worker need about
5 GB of RAM together.

**Revisit if:** The model comparison picks a model that leaves room for embedding on the GPU, or the target GPU
has more memory.

## D-002: Keyword search only joins when a question cites a provision
**Date:** 2026-11-07 · **Status:** Accepted

**Context:** The keyword branch required every query term to match, so it returned nothing on all 45 EU law
questions and on all 189 LegalBench dev queries. Search was vector-only. The fix had to be measured, not assumed.

| Option | Good | Bad | Effort |
|---|---|---|---|
| OR query in Postgres, only when the question cites a provision | Law gain below; LegalBench unchanged; no dependency; access rules stay in SQL | No help for questions with no citation; `ts_rank` is not BM25 | Small |
| OR query always on, with a tuned weight | No special case | Recall@8 falls to 21.5-33.7%, and the one weight that keeps it has a smaller law gain | Small |
| BM25 extension | True BM25 | Not in the pgvector image; BM25 gave 18.5% Recall@8 when merged | Medium |
| In-process BM25 (`bm25s`) | No database change | Same recall loss; a second index to sync; org rules enforced outside SQL | Large |

Merged with vector search by RRF (k=60), LegalBench dev, Recall@8. Vector search alone is 32.6%:

| Keyword weight | 0.1 | 0.2 | 0.3 | 0.5 | 0.7 | 1.0 |
|---|---|---|---|---|---|---|
| OR query in Postgres | 33.7 | 27.4 | 21.5 | 20.1 | 19.4 | 17.2 |
| `bm25s` | 30.1 | 27.2 | 25.1 | 22.2 | 20.5 | 18.5 |

Gold text found on the 45 EU law questions, through `hybrid_search`:

| Top k | Vector only | This decision |
|---|---|---|
| 5 | 73.3% | 86.7% |
| 10 | 77.8% | 91.1% |
| 20 | 93.3% | 95.6% |

**Decision:** Search with an OR query over non-stopword terms, and merge it with vector results only if the question
contains a citation such as "Art. 6", "Artikel 6", "Section 26" or "§ 26". Remove hardcoded query expansion from
retrieval: it changed one of 45 questions, at top 3 only, and looked tuned to the golden set.

**Why:** Keyword search helps with exact references and adds noise elsewhere.

**Why not the others:** No fixed weight kept LegalBench recall and the law gain together. BM25 was only slightly
better than the Postgres query at most weights and still far below vector search alone, so it does not justify a
new image or a second index.

**Consequences:** None of the 6,889 LegalBench queries cite a provision, so that benchmark cannot show this gain. The
law figures are from the project's own questions, which also informed the choice, so they are regression checks
and not results to quote. Failures in keyword search now raise an error instead of silently returning nothing.

**Revisit if:** A public EU benchmark shows keyword search helping questions with no citation.


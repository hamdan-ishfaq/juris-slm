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

## D-003: Keep the LLM's RAM use small while it runs on the GPU
**Date:** 2026-11-07 · **Status:** Accepted

**Context:** Ollama reported Mistral as 100% on the GPU while its `llama-server` runner held 7.5 GB of RAM after a
test run, which is close to everything WSL has. The runner keeps a prompt cache in RAM with a default limit of
8,192 MiB, and it grew by about 0.25 GB per new prompt. Questions rarely repeat, so it saves nothing here. The model
file's memory mapping also added a spike of the model's size while loading.

| Option | Good | Bad | Effort |
|---|---|---|---|
| Turn off the prompt cache and the file mapping | RAM flat at 0.5 GB, same speed and load time | Must be set when starting Ollama; a repeated prompt is processed again | Small |
| Lower the cache limit | Keeps some reuse | Prompts rarely repeat, so it holds RAM for nothing | Small |
| Do nothing | No change | Other jobs get killed once the machine runs out of memory | None |

Measured with 15 distinct prompts of about 1,800 tokens:

| Setting | RAM after 15 prompts | Peak RAM at load | Generation |
|---|---|---|---|
| Defaults | 3.96 GiB and rising | 4.55 GB | 37.8 tokens/s |
| `LLAMA_ARG_CACHE_RAM=0`, `use_mmap` false | 0.50 GiB, flat | 0.49 GB | 38.0 tokens/s |

Load took 2.6-3.3 s without the mapping and 2.7-4.5 s with it.

**Decision:** Start Ollama with `LLAMA_ARG_CACHE_RAM=0`, and send `use_mmap: false` when all layers go to the GPU.

**Why:** It removes all the growth at no measured cost.

**Why not the others:** A smaller cache would still use RAM for prompts that don't come back.

**Consequences:** The setting belongs to the Ollama process, so `.env` can't apply it. `make check-llm-gpu` fails if
the local runner was started without it. An identical repeated prompt gets no reuse, though the query cache already
answers repeated questions earlier in the request.

**Revisit if:** Ollama changes how it starts its runner, or a future prompt design shares a long fixed prefix.

## D-004: Reorder by reranker for law search and cited questions
**Date:** 2026-11-07 · **Status:** Accepted

**Context:** The ms-marco reranker cut LegalBench dev Recall@5 from 26.6% to 17.4%, and only 5 chunks reach the
LLM. It helped EU law questions. Its score also drives the confidence gate, which refuses questions the corpus can't
answer. Reranking runs on the CPU (D-001).

| Option | Good | Bad | Effort |
|---|---|---|---|
| ms-marco reorders law searches and cited questions, scores all | Keeps both gains and the gate | A special case | Small |
| ms-marco always | Simple; best on law | LegalBench Recall@5 17.4% | None |
| No reranker | Simplest and fastest | Law top 3 falls; the gate loses its signal | Small |
| bge-reranker-v2-m3 | Multilingual | 8-12 s per question on CPU; 2.2 GB on disk; no better on either set | Small |

Dev and law figures, retrieval pool of 20:

| Option | LegalBench Recall@5 | LegalBench Recall@8 | Law top 3 | Law top 5 | CPU per question |
|---|---|---|---|---|---|
| No reranker | 26.6 | 32.6 | 75.6 | 86.7 | 0 |
| ms-marco | 17.4 | 24.1 | 86.7 | 88.9 | 0.3-0.5 s |
| bge-reranker-v2-m3 | 23.6 | 32.1 | 84.4 | 88.9 | 8-12 s |

On the 42 law questions with a citation, reordering took top 3 from 76.2% to 85.7% and left top 5 at 88.1%.

Refusal rate by gate threshold, over the top 5 chunks:

| Threshold | -4 | -3 | -2 | -1 | 0 |
|---|---|---|---|---|---|
| LegalBench, asked of its own document | 2.6 | 5.8 | 7.9 | 10.1 | 17.5 |
| LegalBench, asked of a different document | 81.0 | 87.3 | 91.5 | 95.2 | 97.9 |
| Law, answerable (45) | 2.2 | 2.2 | 2.2 | 6.7 | 15.6 |
| Law, should refuse (5) | 60 | 80 | 100 | 100 | 100 |

**Decision:** Score every question with ms-marco. Sort by that score when searching the law corpus or when the
question cites a provision; otherwise keep retrieval order. The gate uses the best score among the chunks kept, with the threshold unchanged at -2.0. Remove
`_boost_art6_basis_hits` and `_boost_section_hits`.

**Why:** It matched the best option on each set where the difference is meaningful, and the -2.0 threshold already
sits at a sensible point: moving it either way trades more than it gains.

**Why not the others:** Always reranking loses a third of LegalBench recall at the point the LLM reads from. No
reranker loses top 3 on law and the gate. The bge model is too slow on a CPU for no measured gain.

**Consequences:** About 8% of answerable contract questions are still refused, which remains a known cost. Sorting
on citations alone was tried first and lost `cross-005`, an uncited law question, every time. Only 3 law questions have
no citation, so that part of the rule rests on little evidence. The contract side rests on LegalBench, whose documents
are US contracts and privacy policies. The boosts changed nothing once reranking ran, and looked tuned to the golden set.

**Revisit if:** A German-capable reranker runs fast enough on a CPU, or a public EU set covers uncited questions.

## D-005: Search a document first when the question names it
**Date:** 2026-11-07 · **Status:** Accepted

**Context:** On LegalBench dev, giving vector search the right document and only the question lifted Recall@8 from 32.6%
to 68.7%. Documents share near-identical clauses, and a document's name in the query pulls search away from the clause
being asked about. The name is usually in the question and in the filename.

| Option | Good | Bad | Effort |
|---|---|---|---|
| Match names to titles, merge named-document results with global ones | 51.4% on dev; a wrong guess can't hide everything else | A name not in the filename isn't found | Small |
| Same, but search only the named document | About the same recall | A wrong route hides all other documents | Small |
| Put the document name in each chunk's embedding | No routing step | Not tried yet; needs a re-embed | Medium |
| Ask the LLM which document is meant | Could handle paraphrase | Adds a model call to each question | Medium |

Recall@8 on LegalBench dev (189 queries):

| Method | Recall@8 | Precision@8 |
|---|---|---|
| Vector, all documents | 32.6 | 5.0 |
| Right document given, question only (a ceiling, not a method) | 68.7 | 10.8 |
| Merged 4:1, with the text after a semicolon (only suits this benchmark's wording) | 54.0 | 8.9 |
| Merged 4:1, general clause rule | 53.2 | 8.8 |
| Merged 4:1, general clause rule, through the product | 51.4 [45.5, 57.4] | 8.5 |

**Decision:** Score document titles against the question, weighting rare and whole words, and route only with a lead of
1.5 over the next title. Search that document with the part of the question after the clause naming it, and merge those
results 4:1 with the global search. Applies to document search, not the law corpus or a question already scoped to a
document.

**Why:** It reached most of the ceiling with no model call. At this lead, all 146 routed dev queries went to the right
document. The general clause rule scored about the same as the benchmark-only form, so the gain doesn't rest on the
benchmark's wording.

**Why not the others:** Strict routing gained nothing over merging and is riskier: 3 of 60 questions naming no document
were still routed, such as one matching a filename containing "Intellectual Property". An LLM call is the slowest
stage, and this works without one.

**Consequences:** LegalBench queries name their document, which favours this method, so the result applies to users who
do the same. Questions that name nothing behave as before. A matched filename word can still route a question naming
nothing, and merging limits the harm.

**Revisit if:** Users refer to documents by names absent from filenames, or a corpus needs titles from document content.


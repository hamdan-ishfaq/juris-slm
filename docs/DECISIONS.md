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
**Date:** 2026-11-07 · **Status:** Accepted; routing rules superseded by D-007

**Context:** On LegalBench dev, giving vector search the right document and only the question lifted Recall@8 from 32.6%
to 68.7%. Documents share near-identical clauses, and a document's name in the query pulls search away from the clause
being asked about. The name is usually in the question and in the filename.

| Option | Good | Bad | Effort |
|---|---|---|---|
| Match names to titles, merge named-document results with global ones | 51.4% on dev; a wrong guess can't hide everything else | A name not in the filename isn't found | Small |
| Same, but search only the named document | About the same recall | A wrong route hides all other documents | Small |
| Put the document name in each chunk's embedding | Also helps questions that aren't routed | Existing documents need a re-embed | Small |
| Ask the LLM which document is meant | Could handle paraphrase | Adds a model call to each question | Medium |

Recall@8 on LegalBench dev (189 queries):

| Method | Recall@8 | Precision@8 |
|---|---|---|
| Vector, all documents | 32.6 | 5.0 |
| Right document given, question only (a ceiling, not a method) | 68.7 | 10.8 |
| Merged 4:1, with the text after a semicolon (only suits this benchmark's wording) | 54.0 | 8.9 |
| Merged 4:1, general clause rule | 53.2 | 8.8 |
| Merged 4:1, general clause rule, through the product | 51.4 [45.5, 57.4] | 8.5 |
| Same, ignoring words in over 5% of titles when routing | 60.0 [54.2, 66.1] | 9.7 |
| Vector, all documents, with the document name embedded | 57.8 [51.7, 63.7] | 9.2 |
| Routing as above, with the document name embedded | 66.2 [60.8, 72.0] | 11.0 |

**Decision:** Score document titles against the question, weighting rare and whole words and ignoring words in over 5%
of titles, and route only with a lead of 1.5 over the next title. Search that document with the part of the question after the clause naming it, and merge those
results 4:1 with the global search. Applies to document search, not the law corpus or a question already scoped to a
document.

Both are adopted: the document name also goes into each contract chunk's embedding.

**Why:** Together they reach most of the ceiling with no model call. With these settings, all 175 routed dev queries went to the right
document. The general clause rule scored about the same as the benchmark-only form, so the gain doesn't rest on the
benchmark's wording.

**Why not the others:** Strict routing gained nothing over merging and is riskier: 3 of 60 questions naming no document
were still routed, such as one matching a filename containing "Intellectual Property". An LLM call is the slowest
stage, and this works without one.

**Consequences:** Documents uploaded before this change need re-embedding to gain from the name in the embedding.
LegalBench queries name their document, which favours this method, so the result applies to users who do the same. Questions that name nothing behave as before. A matched filename word can still route a question naming
nothing, and merging limits the harm.

**Revisit if:** Users refer to documents by names absent from filenames, or a corpus needs titles from document content.

**Amended 2026-11-13:** a wrong route can hide the global results when the routed document has 20 or more chunks;
see D-015.

## D-006: Don't let an English reranker judge German, and trust a retrieved citation
**Date:** 2026-11-07 · **Status:** Accepted

**Context:** D-004 chose ms-marco with no German evidence. On GerDaLIR dev (300 seeded queries, top 100 official BM25
candidates) it cut MRR@10 to about a third of BM25 order. Its score also drives the confidence gate, which refused
"Was regelt § 26 BDSG?" with the § 26 chunk first, and an English question about the BDSG with the right chunk first.

| Ordering on GerDaLIR dev | MRR@10 | nDCG@20 |
|---|---|---|
| BM25, no reranker | 0.326 [0.281, 0.373] | 0.369 |
| bge-m3 similarity | 0.271 [0.228, 0.316] | 0.331 |
| bge-reranker-v2-m3 | 0.238 [0.199, 0.277] | 0.296 |
| ms-marco | 0.112 [0.087, 0.141] | 0.168 |

| Option | Good | Bad | Effort |
|---|---|---|---|
| Detect German; keep retrieval order; skip the gate on German; pass cited provisions that were retrieved | Fixes the failures found; no new model | Some out-of-scope German questions now reach the LLM | Small |
| Replace ms-marco with bge-reranker-v2-m3 | One model for both languages | Worse than no reranker on GerDaLIR; about 6 s per query on the GPU, 8-12 s on CPU | Small |
| Lower the gate threshold | Simple | -3 gained nothing and broke a required refusal; the bad cases scored as low as -9.43 | None |

**Decision:** Questions that look German keep retrieval order. The gate ignores the score if the question or a retrieved
chunk looks German, or if a provision the question cites is among the retrieved chunks. Language is judged by the share of
common German words, which flagged none of 23,363 English chunks, 186 of 202 BDSG chunks and 296 of 300 GerDaLIR queries.

**Why:** A score from a model that can't read the text says nothing. A chunk whose metadata matches the cited provision is
better evidence than that score, and a made-up "Article 999" still matches nothing and is refused.

**Why not the others:** The bge model didn't help German and is too slow. No threshold separates these cases.

**Consequences:** For German there is no retrieval-based refusal, so out-of-scope German questions rely on the LLM's own
answer. GerDaLIR tests reordering of BM25 candidates, not the product's search, and its queries are court decision
passages rather than questions. Keeping retrieval order for German is measured only against ms-marco.

**Revisit if:** A German-capable reranker beats BM25 order on GerDaLIR and runs fast enough on a CPU.

## D-007: Tighten document routing after it failed at scale
**Date:** 2026-11-07 · **Status:** Accepted

**Context:** The routing in D-005 made no errors on 72 documents. On held-out queries over 714 documents, it sent 169 of 859 routed
queries to the wrong document, and the pipeline scored 44.0% Recall@8 against 46.9% for vector search with document names. Ordinary
words in the question matched titles, and a limit based on a share of titles grew with the collection, so words like "disclosure"
counted as names.

| Option | Good | Bad | Effort |
|---|---|---|---|
| Stricter rules: capitalised words in the naming clause, in at most 5 titles, with a lead of 3 | 1 wrong of 320 on the tuning half; 0 of 60 nameless questions routed | Routes fewer queries; a name typed in lowercase isn't routed | Small |
| Remove routing, keep document names in embeddings | Simplest | Gives up a small measured gain, and most of ContractNLI's | Small |
| Ask the LLM which document is meant | Could handle paraphrase | A model call per question, the slowest stage | Medium |

**Decision:** Count only capitalised words other than the first, before the first `;`, `:` or `?`, that appear in at most 5 titles, and
require a lead of 3 over the next title.

**Why:** Tuned on half the held-out documents, then scored once on the other half. The pipeline reached 39.1% [36.6, 41.6] against 36.8%
[34.2, 39.4] for vector search with document names, a paired gain of 2.3 points [1.2, 3.4], and 16.7% for plain vector search.

**Why not the others:** Removing routing gives up a real if modest gain. An LLM call isn't justified yet.

**Consequences:** 20 of 407 routed queries on the final set still went wrong, mostly in CUAD, where 14 of 39 did. Most of the total
gain comes from document names in embeddings, not routing. This held-out set is now used, so further tuning needs new unseen data.

**Revisit if:** CUAD-style filenames matter to users, or wrong routes show up in practice.

## D-008: Trace with OpenTelemetry, sent only to a local collector
**Date:** 2026-11-07 · **Status:** Accepted

**Context:** The Langfuse client couldn't work: its auth header wasn't base64-encoded, it made a blocking request from async code,
each step became a separate trace, and the default host was Langfuse's cloud, wrong for an offline product.

| Option | Good | Bad | Effort |
|---|---|---|---|
| OpenTelemetry, exported only when `OTEL_EXPORTER_OTLP_ENDPOINT` is set | Standard; one trace per question; works offline with Jaeger or any collector | Three packages | Small |
| Repair Langfuse, self-hosted | Rich LLM view | Langfuse v3 needs Postgres, ClickHouse, Redis and S3, too heavy for a 16 GB machine | Large |
| Prometheus and logs only | Nothing new | No per-request trace | None |

**Decision:** Spans for each stage form one trace per question and go to a collector only if one is configured. They carry sizes,
counts and the answer mode, never question or answer text.

**Why:** A per-request trace without a cloud default or a heavy stack.

**Consequences:** Nothing is traced unless an operator points it at a collector. Stage times are also in Prometheus and in each
response, so timing doesn't depend on a collector.

## D-009: Stream a draft, then the checked answer
**Date:** 2026-11-07 · **Status:** Accepted

**Context:** The stream path was a separate copy of the pipeline that skipped the citation check, the extractive fallback, the cache,
the graph context, and a document access check, and the router stored the unchecked draft. The air-gap UI polled a job instead.

| Option | Good | Bad | Effort |
|---|---|---|---|
| Stream draft tokens, then a final event with the checked answer, through one shared pipeline | Tokens arrive at once; what's stored is checked | The answer can change after it appears | Medium |
| Don't stream; return only checked answers | Simple | Waits for the whole answer | Small |
| Check while streaming | No replacement step | The checks need the whole answer | Large |

**Decision:** Sync and streaming requests share `_prepare` and `_finish`. A stream sends draft tokens, then one `final` event with the
checked answer and `replaced` set if it differs. The checked answer is what's stored and audited. The UI streams in every profile,
labels the draft, and says when the checks replaced it.

**Consequences:** A reader may see a draft change. The first token arrives after retrieval, and the checks add about 0.7 s at the end.

## D-010: Use Qwen3 8B as the generator
**Date:** 2026-11-07 · **Status:** Accepted

**Context:** Mistral 7B was chosen before any measurement. The LLM has to run fully on the 6 GB GPU (D-001).

Same 30 seeded LegalBench dev questions with the product's retrieved context, the product's Ollama options and thinking off; judged
by `llama3.1:8b`, which isn't a candidate. German: 8 BDSG questions, the project's own.

| Model | GPU | First token p50 | Answer p50 / p95 | Tokens/s | Faithfulness | Relevancy | Valid JSON | Quote found in text | German replies |
|---|---|---|---|---|---|---|---|---|---|
| Mistral 7B | 100% | 0.44 s | 4.9 / 7.9 s | 38 | 0.81 | 0.81 | 100% | 77% | 5 of 8 |
| **Qwen3 8B** | 100% | 0.39 s | 4.0 / 7.9 s | 34 | 0.82 | **0.84** | 100% | **93%** | **8 of 8** |
| Qwen3.5 4B | 100% | 0.36 s | 4.4 / 7.2 s | 49 | 0.85 | 0.69 | 100% | 93% | 8 of 8 |
| Phi-4-mini | 100% | 0.21 s | 2.1 / 3.2 s | 60 | 0.77 | 0.64 | 100% | 90% | 7 of 8 |
| Gemma 3 4B | 100% | 0.33 s | 2.1 / 4.5 s | 55 | 0.78 | 0.64 | 100% | 73% | 4 of 8 |

In the product, chat latency over 10 law questions went from p50 10.5 s and p95 23.2 s to p50 9.1 s and p95 9.2 s, and the EU suite
from 106 to 105 of 110. Of the three questions that newly failed, two were correct answers missing a gold phrase, and one is the
ambiguous citation listed under the defects.

**Decision:** Qwen3 8B, with thinking off on every request.

**Why:** Best relevancy, German answers every time, quotes that match the text, and faster in the product. Faithfulness differences
between the top models are within the noise of 30 questions and a small judge.

**Why not the others:** Qwen3.5 4B is faithful but answers the question less often. Phi-4-mini and Gemma 3 are faster but weaker on
every quality measure, and Phi-4-mini said "not in the context" on 9 of 30. Larger models don't fit fully on the GPU.

**Consequences:** It uses 5.4 GB of the 6 GB GPU. With thinking left on, Qwen3 spent its token budget on reasoning and returned an empty
answer, so `think: false` is sent on every request. Cold load takes about 42 s, covered by the startup preload.

**Revisit if:** A model that fits the GPU beats it on relevancy and German, or the target GPU grows.

## D-011: Keep five chunks of context
**Date:** 2026-11-07 · **Status:** Accepted

**Context:** More chunks put more of the retrieved evidence in front of the model but make the prompt longer. On the LegalBench mini dev
split, the pipeline's gold text is in the top 4 for 47.7% of queries and the top 8 for 65.1%.

Qwen3 8B on the same 30 seeded LegalBench dev questions, judged by `llama3.1:8b`; the speed for 3 chunks is from a rerun on an idle GPU:

| Chunks | Prompt tokens p50 | First token p50 | Answer p50 / p95 | Faithfulness | Relevancy |
|---|---|---|---|---|---|
| 3 | 716 | 0.25 s | 3.3 / 6.8 s | 0.82 (28 scored) | 0.82 |
| 5 | 974 | 0.39 s | 4.0 / 7.9 s | 0.82 (29 scored) | 0.84 |
| 8 | 1,360 | 0.62 s | 4.1 / 9.5 s | 0.90 (26 scored) | 0.83 |

**Decision:** Keep `rag_rerank_k` at 5 and the 6,000-character cap.

**Why:** No measured difference large enough to act on. The higher faithfulness at 8 rests on fewer scored answers and a small judge.

**Consequences:** These measures don't say whether the answer was found, which is where more chunks should help. The character cap
stays rather than a token budget, since prompts stay well inside the 4,096-token context.

**Revisit if:** An answer-correctness measure on public data shows 8 chunks finding more answers.


## D-012: Don't refuse a question about a chosen document on its retrieval score
**Date:** 2026-11-07 · **Status:** Accepted

**Context:** The confidence gate refuses when the best reranker score is below -2.0, a threshold set on law questions. On BIPIA's
EmailQA emails, uploaded as documents and asked about by name, it refused 103 of 120 questions, so the attack run measured the gate
instead of the defences. The ms-marco reranker scores short emails low even when they hold the answer.

| Option | Good | Bad | Effort |
|---|---|---|---|
| Keep the gate everywhere | one rule | refuses most questions about the user's own short documents | none |
| Recalibrate a second threshold for documents | keeps a refusal path | needs labelled document questions to set it; BIPIA has no unanswerable ones | medium |
| No gate when the user chose the document | the model sees the document it was asked about | a question the document doesn't answer reaches the model | small |

**Decision:** Skip the gate when the question is scoped to a document (`document_id` set). Law and open questions keep it.

**Why:** The user picked the document, so retrieval can't have picked the wrong one; a low score only says the reranker dislikes the
text. The document rule in the prompt tells the model to say when the documents don't answer.

**Why not the others:** Keeping it refuses most real questions about short uploads. A second threshold has no public data to set it on.

**Consequences:** Whether the model declines a question its document doesn't answer is not measured.

**Revisit if:** A public set of unanswerable document questions shows the model answering them anyway.

## D-013: Narrow the injection guard to wording aimed at the model, and don't block on a classifier
**Date:** 2026-11-07 · **Status:** Accepted

**Context:** The regex guard caught 2.5% of attacks on the train split of `deepset/prompt-injections` (pinned revision) and 0% on
test, but blocked 11 of 20 ordinary legal questions that share its words ("Dan signed the NDA", "base64", "bypass security review",
"database credentials"). A direct injection only reaches the attacker's own session: no tools are reachable from an answer, the
system prompt holds nothing secret, and data is scoped by organisation. The larger risk is text inside documents, which the prompt
marks as data; on a fresh BIPIA sample 1 of 120 hidden attacks was followed.

| Option | Good | Bad | Effort |
|---|---|---|---|
| Keep the regex list | no work | blocks legal questions, catches almost no public attacks | none |
| Narrow the regex to wording about the model's instructions | stops blocking legal topics, still stops blatant attempts and oversized input | public recall stays near zero | small |
| `protectai/deberta-v3-base-prompt-injection-v2` as a blocking guard | 36.7% recall on test with no false positives | blocked a real contract question ("What disclosures are permitted?"); its card says English only; about 120 ms and 700 MB per process, in the API and the worker | medium |
| No input guard | simplest | loses the length limit and the cheap block on blatant attempts | small |

Measured on the project's own questions, which were written for the project and are not a benchmark:

| Guard | Law (50) | Contract (20) | Legal lookalikes (20) | Public test recall |
|---|---|---|---|---|
| Regex before | 0 | 0 | 11 | 0% |
| Classifier | 0 | 1 | 2 | 36.7% [25.0, 48.3] |
| Regex after | 0 | 0 | 1 | 0% (train 2.0%) |

**Decision:** Keep only the patterns that address the model's instructions, role delimiters, instruction flooding and the 2,000
character limit. Drop topic words and the second keyword layer. Don't deploy the classifier.

**Why:** The guard's job is not to block lawyers. The defences that matter work on document text, where the attacks come from.

**Why not the others:** The classifier catches a third of public attacks at the cost of blocking real questions and 1.4 GB of RAM in
a 12 GB budget. Keeping the old list blocks more users than attackers. Removing the guard drops the length limit too.

**Consequences:** The input guard is not a defence against injection and the README must say so. Four of the project's own attack
prompts now reach the model and are checked for a safe answer instead of a block. The test split was scored a second time after
this change; the change only removed patterns.

**Revisit if:** Tools, other users' data or secrets become reachable from an answer, or a multilingual classifier blocks no legal questions.

**Amended 2026-11-08:** "decode and execute" is back in the guard. It was removed with the topic word "base64", but it addresses
the model, which is what this decision keeps. Three of the project's own attack prompts now reach the model, not four; the public
and lookalike figures above are unchanged.

## D-014: Don't gate answers on an NLI model yet; describe the current check as a relevance check
**Date:** 2026-11-07 · **Status:** Accepted

**Context:** After generation, an answer is kept if its bge-m3 cosine to a retrieved chunk is at least 0.55 or it shares six
content words with the context; otherwise quoted text replaces it. On ContractNLI (CC BY 4.0), with each hypothesis standing in for
an answer and thresholds tuned on dev, scored once on test (`eval/reports/grounding_2026-11/contractnli_check.md`):

| Check, retrieved spans | Supported passed | Contradicted passed | Not mentioned passed | Balanced accuracy | CPU ms |
|---|---|---|---|---|---|
| Current check | 100.0% | 99.1% | 98.9% | 0.505 | 92 |
| Cosine, tuned | 73.8% | 56.8% | 46.6% | 0.626 | 92 |
| `mDeBERTa-v3-base-xnli-multilingual-nli-2mil7` | 57.4% | 14.5% | 23.6% | 0.678 | 464 |
| `multilingual-MiniLMv2-L6-mnli-xnli` | 43.0% | 13.2% | 23.5% | 0.608 | 37 |

With the annotated evidence instead of retrieved spans, mDeBERTa passed 52.3% of supported and 3.2% of contradicted claims.

| Option | Good | Bad | Effort |
|---|---|---|---|
| Keep the current check | no cost; catches empty, refused and off-topic answers | can't tell a supported claim from a contradicted one | none |
| mDeBERTa as a gate | lets through far fewer contradicted claims | rejects 43% of supported claims, so many correct answers become quoted text; about 0.5 s per sentence on the CPU | medium |
| mDeBERTa as a per-sentence warning | nothing replaced | a warning on about half the correct sentences teaches users to ignore it | medium |
| MiniLM as a gate | fast | worse than mDeBERTa on every column | medium |

**Decision:** Keep the current check and describe it as a relevance check. Don't claim answers are verified against their sources.

**Why:** Both NLI options would cost more correct answers than they protect. Citations are still checked against the retrieved
provision (law and article), which is a separate, working check.

**Why not the others:** A gate halves the supported answers kept. A warning that fires on half the correct sentences carries no signal.

**Consequences:** A fluent answer that contradicts its source can reach the user. ContractNLI is English, so German is untested;
both models are multilingual. Hypotheses are single claims, so real multi-sentence answers would be harder.

**Revisit if:** A check using the contradiction probability, tuned on dev, flags contradictions while passing at least 90% of
supported claims, or a stronger local NLI model fits the CPU budget.

## D-015: When the filename rule finds no document, search the three whose descriptions are nearest the question
**Date:** 2026-11-13 · **Status:** Accepted

**Context:** D-007's rule routes a question to a document when its capitalised words match a filename. It is accurate where it
fires, but CUAD filenames rarely hold the names users write, so most CUAD questions weren't routed: 40.5% Recall@8 on the
held-out tuning half against 76.4% when the right document is given. Tuning on that half (648 queries, 714 documents) and the
mini dev split only; the clean score is a separate set of 1,209 CUAD queries no earlier run used
(`eval/reports/retrieval_round2_2026-11/`).

| Variant, tuning half | Recall@8 | ContractNLI | MAUD | CUAD | Paired vs current |
|---|---|---|---|---|---|
| Current rule | 46.4% | 81.9 | 31.4 | 40.5 | |
| Nearest 3 for every question, weights 4,2,1 | 46.7% | 75.8 | 26.1 | 50.1 | +0.3 [-2.8, +3.2] |
| Rule first, nearest 3 otherwise, 4,2,1 | 49.2% | 79.7 | 30.6 | 49.8 | +2.8 [+0.1, +5.4] |
| Rule first, nearest 3 otherwise, equal weights | 51.3% | 80.8 | 31.2 | 53.8 | +4.8 [+2.5, +7.0] |

A document's description is its filename's words and its first and last paragraphs, embedded. With the document's name removed
(questions asked across all documents), searching the nearest documents dropped Recall@8 from 1.7% to 0.4%, paired -1.3
[-2.3, -0.5]; only doing so when the question has a clause before its first ";", ":" or "?" brings that to +0.0 [+0.0, +0.0].

| Option | Good | Bad | Effort |
|---|---|---|---|
| Rule first, then nearest 3 by description, equal weights, only with a naming clause | +4.8 points on tuning data, no cost to questions naming nothing | A table to fill at ingest; older uploads need re-ingesting to gain | Medium |
| Nearest 3 for every question | Simpler | Hurt ContractNLI and MAUD, where the rule was right | Medium |
| Ask the LLM which document is meant | Could handle paraphrase | A model call per question, the slowest stage | Medium |
| Keep the rule | Nothing to build | Leaves most CUAD questions unrouted | None |

**Decision:** Keep the rule. When it finds nothing and the question has a naming clause, search the three documents whose
descriptions are nearest that clause, each with the rest of the question, and merge them with the global search at equal
weight. Descriptions live in a new `document_descriptions` table (migration 021), keyed by document like `document_chunks`,
written at ingest and deleted with the document.

**Why:** It recovers a third of the gap to a given document on CUAD without a model call, and leaves the rule's correct
routes and questions naming nothing as they were.

**Why not the others:** Searching the nearest documents for every question pulled away from the rule's correct routes. An LLM
call isn't justified while this works without one.

**Consequences:** Weighting fixes a mistake in D-005: with 20 results, a list weighted 4 scores at least 4/80 at every rank,
above anything a list weighted 1 reaches (1/61), so a routed document with 20 or more chunks fills every place and a wrong
route hides the global results. D-005's "a wrong guess can't hide everything else" holds only for short documents. The rule's
4:1 merge is unchanged, since the rule was right on all 291 of its ContractNLI and MAUD routes. Documents uploaded before
this need re-ingesting to get a description; until then they're found as before. The gate is lexical, so "Under the Acme
agreement: what is the term?" is searched by description, and "What does the Acme agreement say about the term?" isn't.

**Revisit if:** Users name documents in ways neither filenames nor first paragraphs carry, or questions across all documents
start being routed.

**Measured 2026-11-13:** on the 1,209 unused CUAD queries, scored once, Recall@8 48.5% [46.0, 51.0] against 35.0% for the
pipeline before this change, paired +13.5 [+11.2, +15.5]. ContractNLI and MAUD, scored a second time, didn't move: +0.4
[-0.8, +1.6] (`eval/reports/retrieval_round2_2026-11/`).

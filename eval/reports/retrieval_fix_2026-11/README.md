# Retrieval fixes, 2026-11-07

The "after" for the [first baseline](../baseline_2026-11/README.md). Code is commit `58536bf` (see `COMMIT`).

## LegalBench-RAG mini, test split

Same dataset, split, scorer, embedder and hardware as the baseline. 587 queries, 95% bootstrap intervals, scored by
the benchmark's own code. The generation model plays no part in these numbers.

| Measure | Baseline | Now |
|---|---|---|
| Pipeline Recall@8 | 25.3% [22.3, 28.3] | **32.8% [29.6, 35.8]** |
| Pipeline Recall@4 | 15.5% | **23.6%** |
| Pipeline Recall@64 | 46.9% | 46.9% |
| Pipeline Precision@8 | 3.5% | **4.6%** |
| Vector search alone, Recall@8 (unchanged) | 32.8% | 32.8% |
| BM25 baseline, Recall@8 (not product code) | 11.1% | 11.1% |

Recall@8 by sub-dataset, baseline to now: privacy policies 30.2% → 50.6%, ContractNLI 43.9% → 49.6%, CUAD 21.6% →
25.1%, MAUD 6.6% → 9.5%. Full tables are in `legalbench_test.md` and `legalbench_dev.md`.

**How to read this**

- The pipeline now equals vector search, and does not beat it. The gain comes from no longer reordering by a reranker
  that made ranking worse on this data. No LegalBench query cites a provision, so the keyword branch never joins here.
- Recall@64 can't rise because the pipeline's candidate pool is 20.
- Tuning used the dev split only. The test split has now been scored twice, baseline and here, with only totals read.
  `BENCHMARK_PLAN.md` asks for one score. No test failure was read, and nothing was tuned on it.
- LegalBench-RAG is US contracts and privacy policies, so this says little about EU statutes.

## Regression checks

These use the project's own questions, which also informed the choices in D-002 and D-004. They catch breakage and
are not results to quote.

| Check | Honest baseline | Now |
|---|---|---|
| EU regression suite | 102 of 110 | 105 of 110 |
| Law questions: gold text in sources / in answer | 86.4% / 90.9% | 95.5% / 97.7% |
| GDPR retrieval gate | 83.3% | 100% |
| Contract questions | 85% | 85% |
| API functional tests | 48 of 48 | 48 of 48 |
| Integration tests | | 41 of 41 |
| Unit tests | 102 | 141 |

The integration run on the host gave 39 passed and 2 failed, both from `sentence_transformers` missing there. Those two
files passed inside the API container: `isolation_tests_in_container.txt`.

Of the 5 remaining suite failures, `cross-003` is a real false refusal: the top score was -2.06 against a threshold of
-2.0. `neg-005`, which must be refused, scored -2.07, so the score can't separate them (`../phase4_retrieval/`). In
earlier runs, the contract failures `ctr-001`, `ctr-013` and `ctr-019` were correct answers missing an exact word, and
the gold answers were left unchanged. `cross-002` has not been analysed.

## Latency

Chat p50 12.6 s, p95 17.7 s over 5 runs on the law corpus, on an RTX 4050 (6 GB), with Mistral-7B 100% on the GPU and
embedding and reranking on the CPU. Only 5 runs, so treat this as indicative. The honest baseline was p50 15.2 s and p95
25.3 s.

## Fixes behind these results

- Keyword search matched nothing on any test question (D-002).
- Reranker reordering only for law search and cited questions (D-004).
- The context cap never counted what it added, and an oversized section emptied the context.
- Statute parsing found no headers. The corpus is now official full text with article metadata.
- `org_id` dropped in multi-query search, and concurrent use of one session in compare.
- Index scans with an access filter could return too few rows (`../phase4_retrieval/hnsw_iterative_scan_after.txt`).
- One org's uploaded corpus reached every tenant, and its text could steer their answers.
- The LLM runner built up 7.5 GB of RAM (D-003).

## Later in this phase

The figures above come from `58536bf`, before document routing and document names in embeddings. The final retrieval score is in
[the held-out report](../heldout_2026-11/README.md).

**Regression checks on the final code** (`final_code/`, commit `75339a1`): EU suite 104 of 110, law questions 95.5% in sources and
95.5% in answers, GDPR gate 100%, API functional tests 48 of 48, chat latency p50 12.8 s and p95 19.7 s over 5 runs. Integration tests:
39 passed on the host, and the 2 that failed there for lack of `sentence_transformers` passed in the container.

**Clean clone:** `clean_clone_reproduction.md` reproduces the dev table on GitHub's CPU runner.

## German: GerDaLIR

Reordering the official top-100 BM25 candidates, passage-wise, by the dataset's official measures. This measures German reranking,
not the product's search, since 3.1 million passages are too many to embed here. 300 seeded queries per split; the test split was
scored once, after the decision was taken on dev.

| Ordering, test split | MRR@10 | nDCG@20 | Dev MRR@10 |
|---|---|---|---|
| BM25, no reranker | 0.345 [0.297, 0.395] | 0.389 | 0.326 |
| bge-m3 similarity | 0.284 [0.237, 0.327] | 0.341 | 0.271 |
| bge-reranker-v2-m3 | 0.244 [0.204, 0.287] | 0.303 | 0.238 |
| ms-marco | 0.141 [0.109, 0.176] | 0.202 | 0.112 |

Recall@100 is 0.631 on test for all of them, fixed by the candidates. The dataset's README publishes 0.365 MRR@10 for BM25 in this mode, which is in line with this sample. On this data, keeping BM25 order beats either reranker.

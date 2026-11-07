# Honest baseline, 2026-11-06

The first run with independent scoring and the LLM fully on the GPU. This is the "before" for the retrieval
fixes. Retrieval on the public benchmark has not changed; see [the first baseline](../baseline_2026-11/README.md).

Law suite, proxy, E2E and latency ran at commit `270e2eb` (see `COMMIT`). RAGAS and the benchmark rerun used the
harness changes committed with this folder.

## Setup

| Item | Value |
|---|---|
| GPU | NVIDIA RTX 4050 Laptop, 6141 MiB |
| Host | WSL2, 11.7 GiB RAM, Docker Desktop |
| Ollama | 0.40.15, `num_gpu` 99, `num_ctx` 4096, one model loaded at a time |
| Generation model | `mistral:7b-instruct-v0.3-q4_K_M` |
| Embeddings, reranker | bge-m3, ms-marco cross-encoder, on CPU ([D-001](../../../docs/DECISIONS.md)) |
| Query expansion | HyDE off, so no aux model call during chat |

## LLM stayed on the GPU

`gpu_check_before.txt` and `gpu_check_after.txt` show 100% for each model. `gpu_samples.txt` has one line every
30 s during the law suite, proxy and E2E: all 33 samples with a model loaded show 100% GPU.

## Results

| Measure | Result | File |
|---|---|---|
| EU regression suite | 102 of 110 (92.7%) | `logical.json` |
| Law questions: gold text in sources | 86.4% of 44 | `logical.json` |
| Law questions: gold text in answer | 90.9% of 44 | `logical.json` |
| `generation_miss` (in sources, not in answer) | 2 (`gdpr-023`, `cross-005`) | `logical.json` |
| Answer in the sources' absence (`retrieval_miss_answer_hit`) | 4 | `logical.json` |
| Answer modes on law questions | 42 LLM, 1 extractive, 1 refused | `logical.json` |
| Contract questions | 85%, with 1 analysis still pending | `logical.json` |
| Refusals correct, forbidden text | 100%, 0 | `logical.json` |
| Benign questions blocked by the injection guard | 11 of 20 | `logical.json` |
| Gold-phrase proxy, first 15 law questions | 100% in sources, 100% in answer | `context_proxy.json` |
| API functional tests | 48 of 48 | `e2e.json` |
| Chat latency over 5 runs | p50 15.2 s, p95 25.3 s | `latency.json` |
| RAGAS faithfulness, LegalBench dev sample | 0.56, 22 of 23 answers scored | `ragas_native.json` |
| RAGAS answer relevancy, same sample | 0.81, 23 of 23 scored | `ragas_native.json` |

`make bench` on the rerun reproduced the [dev table](../bench/results.md) of the first baseline exactly, row for
row, with a fresh database and a new ingest.

## How to read these

- **EU suite:** a regression test, mostly checking for expected phrases. It is the project's own question set, so
  it is not a measure of quality.
- **Comparing with the first baseline's 103 of 110:** that run credited an answer if the gold text was in the
  sources, and retried. This one does neither, so the two are not directly comparable.
- **`retrieval_miss_answer_hit`:** the phrase is in the answer but not in the returned sources. Either the source
  excerpt was cut short or the model answered from its own knowledge. These 4 cases have not been separated yet.
- **Proxy:** 100% only because the first 15 questions are the easy GDPR ones. The 44-question figure above is the
  one to use.
- **Injection guard:** the benign set was written to resemble the guard's patterns, so 11 of 20 shows that it
  over-blocks. It is not an estimate of how often real users would be blocked.
- **Latency:** only 5 runs, on the law corpus. The first baseline's p50 of 28.8 s included a query-expansion call
  and had 11% of the model on the CPU, so the difference is not from the GPU change alone.
- **RAGAS:**
  - 30 seeded dev queries: 23 LLM answers judged, with 4 extractive and 3 refused left out.
  - Answers were generated with the query's own document selected, so this says nothing about finding documents.
  - The judge is `llama3.1:8b`, a small model. Two passes over the same answers gave faithfulness 0.59 and 0.56, so
    small changes mean nothing. Answer relevancy had no valid first pass to compare with.
  - The judge sees each source cut at 2,000 characters, as the API returns it, which can lower faithfulness when
    the model used text past that point.

## Other files

`dev_miss_breakdown.json` groups dev misses by cause. `gate_proof_reversed_ranking.txt` shows the PR gate failing on
a deliberately reversed ranking.

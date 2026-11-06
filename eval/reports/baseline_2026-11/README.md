# Baseline, 2026-11-06

Measurements of the product before any Phase 1+ change. Product code is commit
`528bfe2abe107daea7fae5da7028691596a25d25`. The benchmark harness was uncommitted when these ran
and is added in the commit before this folder.

## Setup

| Item | Value |
|---|---|
| GPU | NVIDIA RTX 4050 Laptop, 6141 MiB, driver 592.82 |
| Host | WSL2, 11.7 GiB RAM, Docker Desktop |
| Ollama | 0.40.15, default `num_ctx` 4096 |
| Generation model | `mistral:7b-instruct-v0.3-q4_K_M` (`6577803aa9a0`) |
| Aux model | `qwen2.5:3b` (`357c53fb659c`) |
| Embeddings, reranker | bge-m3, ms-marco cross-encoder, on GPU |
| Profile | Air-gap latency profile, tracing on, no Langfuse keys (nothing sent out) |
| Law corpus | 1,952 chunks (historic: 1,957). GDPR rebuilt from the EU Cellar API because the download script saves an empty file |

## LegalBench-RAG mini (the only numbers here worth quoting)

Scored with the benchmark's own code. See `eval/legalbench/README.md` for what is pinned and
adapted. Brackets are bootstrap 95% intervals. Test is reported as aggregates only.

| Mode | Dev R@8 (n=189) | Test R@8 (n=587) | Test P@8 | Test R@64 |
|---|---|---|---|---|
| `bm25` (external baseline) | 8.8 [5.7, 12.1] | 11.1 [9.1, 13.3] | 1.4 | 34.8 |
| `fts` (product keyword leg) | 0.0 | 0.0 | 0.0 | 0.0 |
| `dense` | 32.6 [27.1, 37.7] | 32.8 [29.6, 35.8] | 4.6 | 61.7 |
| `hybrid` | 32.6 [27.1, 37.7] | 32.8 [29.6, 35.8] | 4.6 | 61.7 |
| `hybrid_rerank` | 18.6 [14.5, 23.4] | 20.5 [17.7, 23.4] | 2.9 | 61.7 |
| `product` | 24.1 [19.3, 28.8] | 25.3 [22.3, 28.3] | 3.5 | 46.9 (pool of 20) |

- **The keyword leg adds nothing.** `fts` returned zero rows on all 776 queries, so `hybrid` equals
  `dense` at every k.
- **The reranker lowers recall.** Test R@8 falls from 32.8 (`dense`) to 25.3 (`product`), and the
  intervals do not overlap. At R@64 the sets match, so this is ordering and not candidate loss.
- **Harness checks.** 19,393 of 19,393 chunks located (100%), covering 98.0% of corpus characters.
  Scoring matched hand arithmetic and character sets on 15 rows from 5 dev queries with real overlap
  (`experiments/scoring_handcheck.json`). All stored spans equal their chunk text. Only 7 adjacent
  chunk pairs overlap, so the scorer's per-snippet summing does not inflate results.

## Existing suites

| Suite | Result | Note |
|---|---|---|
| Unit tests | 100 of 100 | Host venv, no stack |
| Offline eval | 20 of 20 | Regexes against prompts written for them |
| Logical eval | 103 of 110 (93.6%) | Project's own substring checks. Not a quality score |
| Law `retrieval` / `e2e` | 77.3% / 93.2% | `gen_miss=0` by construction, so these cannot separate retrieval from generation |
| Contract hit rate | 85% | Fixtures are 188 to 798 characters, see H6 |
| Proxy eval | All 1.000 | **Do not use.** It finished in 6 s after logical eval, and its metrics are substring proxies |
| Latency, chat with forced HyDE | p50 28.8 s, p95 30.9 s (5 runs) | Previously recorded: p50 159.7 s |
| E2E | 49 of 49 | `/chat` passed in 25 ms from the query cache, so it did not exercise generation |

The earlier 160 s did not reproduce on this setup. Its cause was not determined: that environment no
longer exists, so a difference in Ollama version or model placement cannot be ruled out or confirmed.

## Hypotheses

| # | Hypothesis | Verdict | Evidence |
|---|---|---|---|
| H1 | Keyword leg is mostly empty | **Confirmed** | Law: 49 of 50 questions empty. LegalBench: 776 of 776. Queries are expanded twice (`expand_legal_query`, `_enhance_legal_fts_query`), then `plainto_tsquery` ANDs every term, so extra terms narrow the match. `consent` becomes `consent & consent & art & 7`: 0 rows, against 145 for `consent` alone. Not an error: controls return rows and no exception fired. `h1_*` |
| H2 | Generation runs to `num_predict` | **Rejected** | 10 of 10 ended with `stop`. Longest was 580 of 1,024 tokens. No Phi-3 markers in answers. `h2_h4_replay.json` |
| H3 | GPU memory contention | **Partly true, corrected again 2026-11-07** | Mistral runs at 11% CPU / 89% GPU, but that split stayed the same with 83, 1,224 and 1,436 MiB already in use on the GPU, so embedding models are not the cause. This row first said "partly confirmed" on that assumption. Measured in `../phase2_removal/gpu_memory_experiment.txt`. Why 11% stays on CPU is open for Phase 5 Later measurement: the 89% split comes from Ollama's estimate and persists at 0 MiB in use, but the API and worker together can hold 5,054 MiB once both have loaded their models, which leaves no room for the LLM at all. See D-001 in `docs/DECISIONS.md`. |
| H4 | Silent prompt truncation | **Rejected as measured** | 143 Ollama requests logged across the replay, suites and upload tests, all `truncated = 0`. Largest law prompt 2,014 tokens. Replay estimates 17 of 774 long-document queries could exceed `num_ctx`, but H6 stops most of those prompts forming. Recheck once H6 is fixed. `h4_*`, `h6_context_assembly.json` |
| H5 | HNSW `ef_search` caps rows | **Not active, risk is real** | Both corpora currently use an exact scan (64 of 64 rows, `dense_exact` identical). An unfiltered plan does cap: `LIMIT 64` gives 41 rows. `h5_explain.txt` |
| H6 | Oversized parent empties the context | **Confirmed** | 79% of chunks have a parent over the 6,000-character cap (largest 401,573). Real upload through `/analyze`: 12 of 20 dev questions got no answer, 8 from this bug and 4 from the rerank confidence gate. Long documents that answer use 1 source. Replay of the benchmark's retrieved chunks: 630 of 774 queries with empty context. `h6_*` |

H6 is invisible to the project's evals because their fixtures are too small to reach the cap.

`h6_real_upload.py` first sent `document_id` to `/chat`, which ignores it. Those results were
discarded and the test re-run through `/analyze`. The script has the corrected version.

## New defects, queued

| Defect | Where | Phase |
|---|---|---|
| Keyword leg empty (H1), double expansion, `ts_rank` labelled BM25 | `vector_store.py:27,266`, `query_enhance.py:11` | 4 |
| Oversized parent empties context (H6); `used` never incremented | `rag.py:179-186` | 4 |
| Reranker lowers recall; `rag_min_rerank_score` refuses answerable questions | `reranker.py`, `rag.py:439` | 4 |
| HNSW row cap when an index plan is chosen (H5) | `vector_store.py` search | 4 |
| `/chat` has no `document_id` and silently ignores it; one long document in scope can blank an answer | `schemas.py:37`, `routers/chat.py:80` | 4 |
| Upload filter rejects commas, as in `Loop Industries, Inc.` | `upload_security.py:24` | 4 |
| Law chunker tags 0 of about 2,515 BGB and 0 of 99 GDPR headers (leading space, no dash) | `law_chunking.py:11` | 4 |
| GDPR download saves an empty file and reports success | `download_assets.py` | 4 |
| BDSG and AI Act files are paraphrased seeds, not statutes | `download_assets.py` | 4 |
| HTML entities left in law text (1,306 lines) | `html_to_plain_text` | 4 |
| Mistral stays 11% on CPU even with the GPU free | Deployment | 5 |
| Cold model load is slow: 37 s measured, about 97 s to first token with disk under load, so a first question after idle can exceed 2 minutes | `keep_alive`, UI | 5 |
| The UI picks `/chat/async` only once `/status` has loaded, so an early Send uses the unverified stream path | `App.jsx:232` | 5 |
| `host.docker.internal` reaches Windows, not WSL, so the compose default cannot reach WSL Ollama | `docker-compose.yml:58` | 5 |
| E2E and proxy eval pass from the query cache | `e2e_functional_test.py`, `run_ragas_eval.py` | 3 |
| Offline eval overwrites the tracked `logical_latest.json` by default | `run_logical_eval.py:302` | 3 |

## Data terms

The scorer repository is MIT licensed. Its README states no separate terms for the dataset, so the
data is not committed: `fetch` downloads it and verifies the checksum.

## Reproducing

`eval/legalbench/README.md` has the benchmark commands. The law questions, replay and upload
experiments are in `experiments/`, each with its run instructions in the docstring. Logical, latency
and E2E runs use the commands in `scripts/run_ollama_eval_complete.sh`, with `--report` pointed here.

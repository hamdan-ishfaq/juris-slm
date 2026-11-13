# Clean clone, 2026-11-13

The plan's final check: a fresh `git clone` of commit `f2b5479`, set up only by following the README, then every suite run
against it. The clone ran as its own compose project (`COMPOSE_PROJECT_NAME=jurisguardclean`) with fresh volumes, on the
reference laptop (RTX 4050 6 GB, 12 GB RAM for WSL). The main stack was stopped for the run and restored afterwards.
Models were hard-linked from the main checkout instead of downloaded again (`make models` reads the same files); the law
corpus was downloaded with `make download-law`.

## Result

| Step | Result | File |
|---|---|---|
| Host virtualenv from `backend/requirements-ci.txt` | Installed | `venv.txt` |
| `make download-law` | 4 laws, 2.6 MB | `download_law.txt` |
| `make up`, `make migrate` | API healthy; `alembic upgrade head` exited 0 | `up.txt`, `migrate.txt` |
| Law ingest | 4,129 chunks; citation graph 2,766 provisions, 3,620 references (same as the main stack) | `ingest_law.txt` |
| `make check-llm-gpu` | qwen3:8b and qwen2.5:3b 100% on the GPU, before and after the bench | `gpu_check*.txt` |
| `make test-unit` | 250 passed, after one fix (below) | `unit.txt` |
| `make retrieval-gate` | Hit rate 1.0, keyword leg non-empty 1.0, no misses | `retrieval_gate.txt` |
| `make e2e` | 48 of 48 passed, 72.8 s | `e2e.txt` |
| Playwright UI suite | 15 of 15 passed, 1.3 min, including a real question streamed as a draft and replaced by the checked answer | `playwright.txt` |
| Integration tests in the ML image (isolation, RBAC, gap analysis, user erasure) | 7 passed, none skipped, 2 min 51 s | `integration.txt` |
| `make mcp-up` and `eval/mcp/live_check.py` | 401 without a token and with a wrong one; exactly the 3 tools; `check_citation` found GDPR Art. 37 and BDSG § 38 and flagged Art. 999 as absent | `mcp_live_check.json` |
| `BENCH_GPU=1 make bench` (LLM unloaded) | Table below | `bench_results.md`, `bench_results.json`, `bench.txt` |
| Egress capture, API and worker | 0 IPv4 packets to a public address, 0 IPv6 beyond link-local; only connections were to Redis in the compose network | `egress_api.txt`, `egress_worker.txt` |

The outbound network wasn't blocked for this run, since several steps download (the law corpus, the images' packages,
Playwright's browser). Instead the running API and worker were captured while a question and an upload were processed,
as in `eval/reports/security_2026-11/`.

The whole run took 1 h 41 min. About 40 minutes of it was downloading CUDA PyTorch for the GPU bench image at 1-1.5 MB/s.

## Bench against the committed table

LegalBench-RAG mini dev (189 queries), Recall@8:

| Mode | Committed (`53db67b`, `eval/reports/bench/`) | Clean clone (`f2b5479`) |
|---|---|---|
| bm25 | 8.8 | 8.8 |
| fts | 7.2 | 7.2 |
| dense | 57.8 | 57.8 |
| hybrid | 57.8 | 57.8 |
| hybrid_rerank | 21.9 | 21.9 |
| product | 65.1 | 67.1 |

Every mode the code hasn't changed since `53db67b` reproduced to the decimal, at every cutoff. The product mode moved
because the pipeline did: document routing by description (D-015) and the later retrieval work came after that table.

## What the clean clone found

Each was fixed on the branch, and the run was repeated or the step re-run:

1. **First attempt:** `make models` and `make download-law` ran the system `python3`, which lacks `tqdm` and `requests`,
   and the README never created the host virtualenv. Law ingest then reported success with 0 chunks. Fixed in `f2b5479`:
   the targets use `.venv`, the host requirements list the download tools and `bm25s`, and ingest fails when no law file
   is present.
2. **Found while preparing the run:** the egress check hard-coded the compose project name `jurisguard`, and the MCP
   service had no image of its own, so a second checkout would have stopped the wrong container or retagged the API
   image. Fixed in `fe1eb5e`.
3. **This attempt:** `make test-unit` failed with "pytest: not found". CI installs pytest separately; the README setup
   doesn't. Fixed in `a3a922b` (pytest added to `requirements-ci.txt`), installed into the clone's venv, and the unit step
   re-run: 250 passed.

Not covered by eye: the Playwright suite asks a real question through the UI and the integration test runs a gap report
against the live LLM, but neither answer was read by a person in this run.

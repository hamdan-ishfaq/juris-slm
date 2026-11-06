# JurisGuard

[![CI](https://github.com/hamdan-ishfaq/juris-slm/actions/workflows/ci.yml/badge.svg)](https://github.com/hamdan-ishfaq/juris-slm/actions/workflows/ci.yml)

Legal teams often can't send client documents to a cloud AI service. JurisGuard is a self-hosted
research assistant for that case: it answers questions over EU and German law and uploaded contracts,
cites its sources, and can run with no outbound network, on a single consumer GPU.

**Status: in development, not in production use.** Measuring it against a public benchmark exposed
serious retrieval defects, listed below. They are being fixed, and the numbers here will be replaced
as that happens.

## What it does

- **Research chat** over GDPR, BGB, BDSG and the EU AI Act.
- **Matter workspace**: upload contracts, ask questions about a document, compare documents, export.
- **Gap analysis** of a contract against the law. This is currently rule-based, with no LLM steps.
- **Access control**: organisation isolation, roles, row-level security and a hash-chained audit log.
- **Local by default**: embeddings, reranking and generation can all run on your own hardware.

## How a question is answered

```
question → injection guard → cache → hybrid search → rerank → LLM → citation check → audit log
                                     (pgvector + keyword)   (Ollama)
```

FastAPI, PostgreSQL with pgvector, Redis, Celery, React, Ollama. bge-m3 embeddings and an ms-marco
cross-encoder reranker.

## Measured results

Retrieval on the [LegalBench-RAG](https://github.com/zeroentropy-ai/legalbenchrag) mini set, scored by
the benchmark's own code. Test split, 587 queries, with 95% bootstrap intervals.

| Method | Recall@8 | Precision@8 | Recall@64 |
|---|---|---|---|
| BM25 baseline (not product code) | 11.1% [9.1, 13.3] | 1.4% | 34.8% |
| Vector search alone | 32.8% [29.6, 35.8] | 4.6% | 61.7% |
| **JurisGuard pipeline** | **25.3% [22.3, 28.3]** | 3.5% | 46.9%* |

\* The pipeline's candidate pool is 20, so k above 20 can't improve it.

**The full pipeline currently scores below vector search alone**, because of the first two defects
below. Chat latency is p50 28.8 s and p95 30.9 s over 5 runs on an RTX 4050 (6 GB) with Mistral-7B,
including a query-expansion model call.

These are 2026-11-06 baseline figures from before any fixes.
[Full report, setup and method](eval/reports/baseline_2026-11/README.md).

LegalBench-RAG is built on US contracts and privacy policies. The project's own 110-case EU regression
suite passes 103 of 110, but it mostly checks for expected phrases, so it is a regression test and not
a measure of quality.

## Known defects

| Defect | Effect |
|---|---|
| Keyword search requires every query term to match | Returned nothing on all 776 benchmark queries, so "hybrid" search is really vector-only |
| Reranker makes ordering worse on this data | Recall@8 falls from 32.8% to 25.3% |
| Oversized contract sections empty the prompt context | 12 of 20 test questions on real long contracts got no answer: 8 from this, 4 from the confidence gate |
| Law chunker misses article and section headers | Citations can't rely on chunk metadata |
| BDSG and EU AI Act files are short paraphrases, not the statutes | Answers on them are thin. Official texts are being added |
| `make download-law` saves an empty GDPR file and reports success | The law corpus has no GDPR text until this is fixed |

The first report lists the rest. The citation check is also weak today: it looks for an article number
anywhere in the sources, not within the cited one.

## Quickstart

Needs Docker, and optionally an NVIDIA GPU. [Ollama](https://ollama.com) runs on the host.

```bash
git clone https://github.com/hamdan-ishfaq/juris-slm.git
cd juris-slm
cp .env.example .env          # set AUTH_SECRET_KEY (32+ characters)

ollama pull mistral:7b-instruct-v0.3-q4_K_M
ollama pull qwen2.5:3b

make models && make download-law
make up
make check-llm-gpu            # fails unless the LLM is fully on the GPU
make ingest-law-docker
make ui-dev                   # http://localhost:5173
```

For local use with no cloud LLM, start from `.env.airgap.example`. Under Docker Desktop on WSL,
`host.docker.internal` reaches Windows rather than your distro, so if Ollama runs inside WSL, set
`OLLAMA_BASE_URL` to the address from `hostname -I`. That address can change on reboot.

On a 6 GB GPU the LLM takes the whole GPU, and embedding and reranking run on the CPU
([why](docs/DECISIONS.md)). Start Ollama with `OLLAMA_MAX_LOADED_MODELS=1` so a second model can't
share the GPU with it. Allow about 5 GB of RAM for the API and worker.

| Port | Service |
|---|---|
| 8002 | API (`/docs` for OpenAPI) |
| 5173 | UI, dev server |
| 5433 | Postgres |
| 6380 | Redis |
| 11434 | Ollama, on the host |

## Tests and benchmarks

```bash
make test-unit       # unit tests, no stack needed
make e2e             # API functional tests against a running stack
make eval-offline    # RBAC and injection regression checks
make eval-logical    # EU regression suite, needs a running stack and Ollama
```

The LegalBench harness and its commands are in [`eval/legalbench/`](eval/legalbench/README.md).

## Layout

```
backend/src/    API, RAG pipeline, workers
backend/alembic/  database migrations
frontend/src/   React UI
eval/           golden sets, benchmark harness, reports
scripts/        setup, ingest and eval scripts
experiments/    earlier fine-tuning work, not part of the product
```

[`COMPLETE_PROJECT_HANDOFF.md`](COMPLETE_PROJECT_HANDOFF.md) has the API, schema and configuration
reference. Some of its figures predate the baseline above; where they differ, the baseline report is
correct.

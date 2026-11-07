# JurisGuard

[![CI](https://github.com/hamdan-ishfaq/juris-slm/actions/workflows/ci.yml/badge.svg)](https://github.com/hamdan-ishfaq/juris-slm/actions/workflows/ci.yml)

Legal teams often can't send client documents to a cloud AI service. JurisGuard is a self-hosted
research assistant for that case: it answers questions over EU and German law and uploaded contracts,
cites its sources, and can run with no outbound network, on a single consumer GPU.

**Status: in development, not in production use.** Results come from public benchmarks and include what
went wrong. The known defects are listed below.

## What it does

- **Research chat** over GDPR, BGB, BDSG and the EU AI Act.
- **Matter workspace**: upload contracts, ask questions about a document, compare documents, export.
- **Gap analysis** of a contract against the law. This is currently rule-based, with no LLM steps.
- **Access control**: organisation isolation, roles, row-level security and a hash-chained audit log.
- **Local by default**: embeddings, reranking and generation can all run on your own hardware.

## How a question is answered

```
question → injection guard → cache → find a named document → vector search, plus keyword search for citations
         → rerank where it helps → LLM (Ollama) → citation check → audit log
```

FastAPI, PostgreSQL with pgvector, Redis, Celery, React, Ollama. bge-m3 embeddings and an ms-marco
cross-encoder reranker.

## Measured results

### Retrieval: LegalBench-RAG

Scored by the [benchmark's](https://github.com/zeroentropy-ai/legalbenchrag) own code, on 1,135 queries about documents that played no
part in tuning, searching all 714 documents. 95% bootstrap intervals.

| Method | Recall@8 | Precision@8 |
|---|---|---|
| BM25 baseline | 3.8% [2.8, 4.9] | 0.6% |
| Plain vector search | 16.7% [14.6, 18.8] | 2.3% |
| Vector search, with document names embedded | 36.8% [34.2, 39.4] | 5.7% |
| **JurisGuard pipeline** | **39.1% [36.6, 41.6]** | **6.1%** |

By sub-dataset: ContractNLI 83.3%, CUAD 38.4%, MAUD 27.8%. Compared query by query, the pipeline gains 22.4 points [19.8, 24.9] over plain
vector search, and 2.3 points [1.2, 3.4] over vector search with document names.

Two things to keep in mind:

- Every query in this benchmark names its document, which is what these methods use. Questions that name no document get much less from
  them, and this is US contracts rather than EU law.
- The first clean score was a failure, at 44.0% against 46.9% for vector search with names, because routing broke at scale. After fixing
  it on half the held-out documents, this score comes from the other half.

[Full report, with every attempt](eval/reports/heldout_2026-11/README.md).

### German reranking: GerDaLIR

Reordering the dataset's official top-100 BM25 candidates, on 300 seeded test queries. This measures reranking only, since its 3.1 million
passages are too many to embed here.

| Ordering | MRR@10 | nDCG@20 |
|---|---|---|
| **BM25, no reranker** | **0.345 [0.297, 0.395]** | **0.389** |
| bge-m3 similarity | 0.284 [0.237, 0.327] | 0.341 |
| bge-reranker-v2-m3 | 0.244 [0.204, 0.287] | 0.303 |
| ms-marco | 0.141 [0.109, 0.176] | 0.202 |

So German questions don't use the reranker for ordering. [Report](eval/reports/retrieval_fix_2026-11/README.md).

### Speed and memory

On an RTX 4050 (6 GB) with Mistral-7B 100% on the GPU: chat latency p50 12.8 s and p95 19.7 s over 5 runs on the law corpus, about 38 tokens
per second, and 0.5 GB of RAM held by the LLM. Only 5 runs, so treat the latency as indicative. [How the memory is split](docs/DECISIONS.md).

### Regression suite

The project's own 110-case EU suite passes 104 of 110. It mostly checks for expected phrases, and these questions informed some design
choices, so it is a regression test and not a measure of quality. A RAGAS run on 23 public answers, from before these fixes, gave faithfulness
0.56 and answer relevancy 0.81, judged by a small local model.

## Known defects

| Defect | Effect |
|---|---|
| Document routing depends on names in filenames | 14 of 39 routed CUAD queries went to the wrong document, and most CUAD queries aren't routed |
| Long merger agreements retrieve poorly | MAUD Recall@8 is 27.8%, mostly from finding the wrong section of the right document |
| Keyword search only helps questions citing a provision | Other questions rely on vector search alone. See [D-002](docs/DECISIONS.md) |
| About 8% of answerable contract questions are refused | Measured on the mini set's dev split |
| No retrieval-based refusal for German questions | Out-of-scope German questions rely on the LLM's own answer |
| Uploaded document text reaches the prompt unguarded | A malicious document can steer answers within its own org |
| The citation check is weak | It looks for an article number anywhere in the sources, not within the cited one |
| An article number without the law's name can retrieve the wrong statute | "What does Article 12 require?" matched the AI Act, and the fallback quoted it |

Documents uploaded before document names went into embeddings need re-embedding to gain from it.

## Quickstart

Needs Docker, and optionally an NVIDIA GPU. [Ollama](https://ollama.com) runs on the host.

```bash
git clone https://github.com/hamdan-ishfaq/juris-slm.git
cd juris-slm
cp .env.example .env          # set AUTH_SECRET_KEY (32+ characters)

ollama pull qwen3:8b
ollama pull llama3.1:8b       # only for make eval-native, as the judge
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
([why](docs/DECISIONS.md)). Start Ollama like this, so a second model can't share the GPU and the LLM
doesn't build up a cache in RAM. Allow about 5 GB of RAM for the API and worker.

```bash
LLAMA_ARG_CACHE_RAM=0 OLLAMA_MAX_LOADED_MODELS=1 OLLAMA_NUM_PARALLEL=1 ollama serve
```

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
make retrieval-gate  # retrieval check on committed fixtures, runs on every PR
make bench           # reproduces the LegalBench mini table, needs the GPU free or BENCH_GPU=0
make eval-native     # RAGAS on public dev queries, after make bench
```

The LegalBench harness and held-out evaluation are in [`eval/legalbench/`](eval/legalbench/README.md), and the GerDaLIR harness is in
[`eval/gerdalir/`](eval/gerdalir/gerdalir.py). Design decisions are in [`docs/DECISIONS.md`](docs/DECISIONS.md).

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

# JurisGuard

[![CI](https://github.com/hamdan-ishfaq/juris-slm/actions/workflows/ci.yml/badge.svg)](https://github.com/hamdan-ishfaq/juris-slm/actions/workflows/ci.yml)

Legal teams often can't send client documents to a cloud AI service. JurisGuard is a self-hosted
research assistant for that case: it answers questions over EU and German law and uploaded contracts,
cites its sources, and runs with no outbound network on a single consumer GPU.

**Status: in development, not in production use.** Results come from public benchmarks and include what
went wrong. The known defects are listed below.

## What it does

- **Research chat** over GDPR, BGB, BDSG and the EU AI Act.
- **Matter workspace**: upload contracts, ask questions about a document, compare documents, export.
- **Gap analysis** of a contract: a checklist review that searches the contract for each clause type, asks the model
  for a verbatim quote, and checks the quote against the text.
- **Access control**: organisation isolation, roles, row-level security and a hash-chained audit log.
- **MCP server** (read-only): assistants such as Claude Code can search the law, read a provision and check citations
  over MCP, behind a hashed bearer token, every call audited ([report](eval/reports/mcp_2026-11/README.md)).
- **Local**: embeddings, reranking and generation run on your own hardware; a packet capture shows no connection leaves it.

## How a question is answered

```
question → injection guard → cache → find a named document → vector search, plus keyword search for citations
         → rerank where it helps → follow a cited provision's references → LLM (Ollama, streamed)
         → relevance and citation checks → audit log
```

FastAPI, PostgreSQL with pgvector, Redis, Celery, React, Ollama with Qwen3 8B. bge-m3 embeddings and an ms-marco
cross-encoder reranker. Each stage is timed in Prometheus at `/metrics`, and traces go to an OpenTelemetry collector if one is set.

## Measured results

### Retrieval: LegalBench-RAG

Scored by the [benchmark's](https://github.com/zeroentropy-ai/legalbenchrag) own code, searching all 714 documents, with 95% bootstrap
intervals. Three findings:

1. **Most of the gain comes from putting each document's name into its chunks' embeddings.** On the first held-out set (1,135
   queries), that alone took plain vector search from 16.7% to 36.8% Recall@8. The rest of the pipeline adds 2.3 points
   [1.2, 3.4] on top, query by query, for 39.1% [36.6, 41.6].
2. **Finding the right contract is the hard part.** Asked inside the right document, CUAD recall is 73%; left to find it among
   714, the old pipeline got 35%. Searching the three documents whose descriptions are nearest the question, when filenames
   don't match ([D-015](docs/DECISIONS.md)), closed part of that gap. On 1,209 CUAD queries no earlier run had touched:

   | Method | Recall@8 | Precision@8 |
   |---|---|---|
   | BM25 | 6.2% [4.9, 7.5] | 0.9% |
   | Plain vector search | 24.9% [22.6, 27.1] | 3.6% |
   | Vector search, with document names embedded | 35.3% [33.1, 37.8] | 5.2% |
   | Pipeline before D-015 | 35.0% [32.7, 37.5] | 5.1% |
   | **JurisGuard pipeline** | **48.5% [46.0, 51.0]** | **6.1%** |

   Query by query, +13.5 points [+11.2, +15.5] over the pipeline before, and 1.9 times plain vector search.
3. **It depends on the question naming its document.** With the name removed, the same questions find 0.8% across 714
   contracts, because "Is there a cap on liability in this contract?" doesn't say which contract. Picking the document in
   the interface instead gives 73.1%.

Things to keep in mind:

- This is US contracts and privacy policies, not EU law. Only CUAD had unused queries left, so ContractNLI and MAUD were
  scored a second time instead: 84.0% and 28.1%, unchanged by D-015. MAUD stays weak even inside the right document.
- On the benchmark's 72-document mini set (test split, scored a third time), the pipeline reaches 60.9% [57.4, 64.2] against
  50.5% for vector search with names. Fewer documents means less to confuse, so it isn't comparable with the 714-document
  figures.
- The first clean score failed, at 44.0% against 46.9% for vector search with names, because routing broke at scale. It was
  fixed on half the held-out documents and scored on the other half. Larger or overlapping chunks didn't help on the same
  amount of text.

[Second round](eval/reports/retrieval_round2_2026-11/README.md), [first held-out round](eval/reports/heldout_2026-11/README.md),
both with every attempt.

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

On an RTX 4050 (6 GB) with Qwen3 8B 100% on the GPU, chat latency is p50 9.1 s and p95 9.2 s over 10 law questions, of which
generation is 7.8 s. Answers stream: the first token arrives about 0.4 s after retrieval, and the checked answer follows when generation
ends. A repeated question comes from the cache in 37 ms. The LLM holds 0.8 GB of RAM and stays loaded, so the first question after a
restart takes about 4.5 s. Before this work, p50 was 28.8 s and the first question after a restart took 130 s.

Only one model fits the GPU at a time, so running evaluations while serving users slows both.
[Stage timings and decisions](eval/reports/llm_latency_2026-11/), [memory layout](docs/DECISIONS.md).

### Choosing the model

Five models that fit fully on 6 GB, on the same 30 public LegalBench questions with the product's context, judged by a different model:

| Model | Answer p50 / p95 | Faithfulness | Relevancy | Quote found in text | German replies |
|---|---|---|---|---|---|
| **Qwen3 8B (used)** | 4.0 / 7.9 s | 0.82 | **0.84** | **93%** | **8 of 8** |
| Mistral 7B (before) | 4.9 / 7.9 s | 0.81 | 0.81 | 77% | 5 of 8 |
| Qwen3.5 4B | 4.4 / 7.2 s | 0.85 | 0.69 | 93% | 8 of 8 |
| Phi-4-mini | 2.1 / 3.2 s | 0.77 | 0.64 | 90% | 7 of 8 |
| Gemma 3 4B | 2.1 / 4.5 s | 0.78 | 0.64 | 73% | 4 of 8 |

30 questions and a small judge make faithfulness differences of a few hundredths noise. [Decision and method](docs/DECISIONS.md).

### Regression suite

The project's own 110-case EU suite passes 107 of 110 on the current code; recent runs ranged from 106 to 108, because the model's
wording varies between runs (one question cited its article in 1 of 3 tries). It mostly checks for expected phrases, and these questions informed some design
choices, so it is a regression test and not a measure of quality. A RAGAS run on 23 public answers, from before these fixes, gave faithfulness
0.56 and answer relevancy 0.81, judged by a small local model.

### Gap analysis: CUAD

Which of 10 clause types (governing law, anti-assignment, liability cap, audit rights and others) each contract has, on 100
CUAD test contracts scored once, 1,000 decisions:

| Method | Accuracy | Clauses wrongly reported missing |
|---|---|---|
| **Checklist review** | **83.5% [81.1, 86.1]** | **126** |
| One call over the contract's opening | 62.3% [57.8, 66.9] | 368 |
| The rule-based tool it replaced | 56.7% [52.9, 60.6] | 347 |
| Reporting every clause missing | 57.9% | 421 |

Its quote overlapped CUAD's annotated answer 89.5% of the time. It errs towards "missing", and on exclusivity and change of
control it does no better than calling the clause missing ([D-017](docs/DECISIONS.md),
[report](eval/reports/gap_agent_2026-11/README.md)).

### Following citations between provisions

A graph of which provision refers to which, read by rule from the four statutes: 2,766 provisions and 3,620 references, with
the parser at 95.2% precision and 90.9% recall on a hand-checked sample. When a question cites a provision, the pipeline
finds it by law and article and adds up to two provisions it cites or is cited by, with the path shown in the sources
("GDPR Art. 30 → GDPR Art. 9"). On the project's own questions whose answer is in a linked provision, the right provision
reached the model in 11 of 15 held-out questions, from 9, and no question lost it. It costs about 0.7 s a law question on
the CPU. The sets are small and the project wrote them, so this shows it helps a few questions, not a rate
([D-016](docs/DECISIONS.md), [report](eval/reports/citation_graph_2026-11/README.md)).

### Security and grounding

| Check | Result |
|---|---|
| Attacks hidden in uploaded documents (BIPIA EmailQA, 6 rule-judged attack types, 120 fresh samples) | 0.8% followed [0, 2.5], from 19.2% |
| Direct injection caught by the input guard (`deepset/prompt-injections` test) | 0%; it now blocks 1 of 20 legal lookalike questions, from 11 |
| Does the answer check tell supported from contradicted claims? (ContractNLI test) | No: it passes 99.1% of contradicted claims |
| Connections to public addresses while starting, answering and ingesting | 0, by packet capture of the API and the worker |
| Known vulnerabilities in installed Python packages (pip-audit) | 0 of 129, after upgrading torch and transformers |
| bandit / OWASP ZAP passive API scan | one reviewed low notice / no failures |

The defence against hidden instructions is in how document text reaches the model, not in the input guard. Answers are not checked
against their sources: an NLI model would have turned about half the correct answers into quoted text
([D-014](docs/DECISIONS.md)). [Full report](eval/reports/security_2026-11/README.md).

## What broke and what I changed

The project began as a feature-heavy prototype whose results came from tests written for it. Checked against the code, its
keyword search was silently empty, its "agent" made no model calls, and its headline score counted a right answer anywhere
in the sources. [`docs/BUILD_STORY.md`](docs/BUILD_STORY.md) goes through what was found, what changed and what each change
measured, including the attempts that failed. [`docs/DESIGN.md`](docs/DESIGN.md) has the request path with measured stage
times, the failure modes that were tested and what breaks at ten times the load.

## Known defects

| Defect | Effect |
|---|---|
| Finding the document depends on the question naming it | Without a name, questions across all contracts find 0.8%; with a name, CUAD reaches 48.5% against 73.1% when the document is chosen |
| Long merger agreements retrieve poorly | MAUD Recall@8 is 28.1%, and 30.4% even with the right document given: the loss is finding the section, not the document |
| Keyword search only helps questions citing a provision | Other questions rely on vector search alone. See [D-002](docs/DECISIONS.md) |
| About 8% of answerable contract questions are refused | Measured on the mini set's dev split |
| No retrieval-based refusal for German questions | Out-of-scope German questions rely on the LLM's own answer |
| Answers aren't checked for support | The relevance check passes 99.1% of ContractNLI claims the contract contradicts, so a fluent wrong answer can get through |
| Hidden instructions in documents can still work | 1 of 120 BIPIA attacks was followed: it asked for the reply in French and got it |
| The input guard doesn't stop prompt injection | It catches 0% of public test attacks; it only blocks plain attempts at the model's instructions |
| A question about a chosen document is never refused for weak retrieval | Whether the model declines when the document doesn't answer is unmeasured ([D-012](docs/DECISIONS.md)) |
| A bare article number takes the law of the best retrieved chunk | "What does Article 12 require?" now answers from the GDPR, without saying so; a question meant for the AI Act would get the GDPR |
| The gap analysis over-reports missing clauses | 126 of its 1,000 CUAD test decisions called a present clause missing; exclusivity and change of control are no better than guessing "missing" |
| Following citations only helps one way | Gains came from provisions the cited one refers to; when the answer is in a provision citing the asked one, it didn't gain |

Documents uploaded before document names went into embeddings, or before document descriptions (D-015), need re-ingesting to gain from them.

## Quickstart

Needs Docker, and optionally an NVIDIA GPU. [Ollama](https://ollama.com) runs on the host.

```bash
git clone https://github.com/hamdan-ishfaq/juris-slm.git
cd juris-slm
cp .env.example .env          # set AUTH_SECRET_KEY (32+ characters)
python3.12 -m venv .venv && .venv/bin/pip install -r backend/requirements-ci.txt   # host tools; or: uv venv -p 3.12 .venv

ollama pull qwen3:8b
ollama pull llama3.1:8b       # only for make eval-native, as the judge
ollama pull qwen2.5:3b

make models && make download-law
make up
make check-llm-gpu            # fails unless the LLM is fully on the GPU
make ingest-law-docker
make ui-dev                   # http://localhost:5173
make mcp-up                   # optional read-only MCP server on :8003, see eval/reports/mcp_2026-11
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
| 8003 | Read-only MCP server (`make mcp-up`) |
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

A fresh clone set up only from this README passed all of the above, Playwright and the MCP check, and reproduced the
bench table: [`eval/reports/clean_clone_2026-11/`](eval/reports/clean_clone_2026-11/README.md).

## Layout

```
backend/src/    API, RAG pipeline, workers
backend/alembic/  database migrations
frontend/src/   React UI
eval/           golden sets, benchmark harness, reports
scripts/        setup, ingest and eval scripts
experiments/    earlier fine-tuning work, not part of the product
```

[`COMPLETE_PROJECT_HANDOFF.md`](COMPLETE_PROJECT_HANDOFF.md) has the project status, API, schema and
configuration reference, and the remaining plan.

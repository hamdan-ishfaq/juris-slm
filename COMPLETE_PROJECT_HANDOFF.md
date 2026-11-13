# JurisGuard — Project Handoff

The single reference for how the project is built, run and measured. `README.md` is the short public overview;
`docs/DECISIONS.md` records why things are the way they are. Every number here comes from a report file in
`eval/reports/`, named next to it.

| Field | Value |
|---|---|
| Repo | https://github.com/hamdan-ishfaq/juris-slm |
| Default branch | `master` |
| App version | `0.5.0` (`backend/src/main.py`) |
| Status | In development, not in production use |
| Last updated | 2026-11-13, after Phase 6b (retrieval, second round) |
| Measured on | WSL2, RTX 4050 6 GB, 12 GB RAM for WSL, 8 CPUs, Ollama on the host |

---

## Contents

1. [Summary](#1-summary)
2. [Where the project stands](#2-where-the-project-stands)
3. [Measured results](#3-measured-results)
4. [Known defects](#4-known-defects)
5. [Architecture](#5-architecture)
6. [How a question is answered](#6-how-a-question-is-answered)
7. [Models and memory layout](#7-models-and-memory-layout)
8. [Features](#8-features)
9. [Repository layout](#9-repository-layout)
10. [Tech stack](#10-tech-stack)
11. [Database](#11-database)
12. [API](#12-api)
13. [Frontend](#13-frontend)
14. [Workers](#14-workers)
15. [Auth and security](#15-auth-and-security)
16. [Configuration](#16-configuration)
17. [Data and storage](#17-data-and-storage)
18. [Setup and operations](#18-setup-and-operations)
19. [Testing](#19-testing)
20. [Evaluation and benchmarks](#20-evaluation-and-benchmarks)
21. [CI](#21-ci)
22. [Decisions log](#22-decisions-log)
23. [Remaining plan](#23-remaining-plan)
24. [Conventions](#24-conventions)
25. [Day-one checklist](#25-day-one-checklist)

---

## 1. Summary

Legal teams often can't send client documents to a cloud AI service. JurisGuard is a self-hosted research assistant
for that case. It answers questions over EU and German law (GDPR, BGB, BDSG, EU AI Act) and over uploaded contracts,
cites its sources, and runs with no outbound network on one consumer GPU.

- **Research chat** over the law corpus, streamed, with sources and checked citations.
- **Matter workspace**: upload contracts, ask about one document, compare documents, export reports.
- **Gap analysis** of a contract against the law. Rule-based today: regex and keyword counts, no LLM calls.
- **Access control**: organisation isolation, roles, row-level security, hash-chained audit log.
- **Local**: embeddings, reranking and generation run on the machine. A packet capture of the API and worker showed
  no connection to a public address.

---

## 2. Where the project stands

The project is being reworked in phases from a plan that checked every earlier claim against the code. Each phase
ends only when its checks pass and its reports are saved, and is then merged to `master`.

| Phase | Theme | Merged | Outcome |
|---|---|---|---|
| 0 | Baseline | `c0cf26b` | Stack rebuilt; honest "before" numbers; LegalBench-RAG harness |
| 1 | Repo cleanup | `801f06a` | `v2/` moved to root; gitleaks clean; README rewritten |
| 2 | Remove enterprise features | `5e49965` | SSO, SCIM, WORM, legal hold, clause library and deadlines removed (migration 019) |
| 3 | Honest evals | `0125a7a` | Retrieval and answers scored separately; `answer_mode`; `make bench`; retrieval gate on PRs |
| 4 | Retrieval | `ed523e5` | Document routing, keyword search for citations, reranker policy; held-out LegalBench score |
| 5 | LLM and latency | `4463cb8` | Qwen3 8B chosen by measurement; `/api/chat`; streaming; stage metrics; OpenTelemetry |
| 6 | Grounding and security | `859a519` | BIPIA, injection, ContractNLI, egress capture, bandit, pip-audit, ZAP |
| 6b | Retrieval, second round | `feature/retrieval-round2` | Search nearest-described documents when filenames don't match (D-015); chunker unchanged |
| 7 | Citation graph | not started | See §23 |
| 8 | Gap-analysis agent | not started | |
| 9 | Read-only MCP server | not started | |
| 10 | Docs and clean-clone proof | not started | |

Phase reports: `eval/reports/baseline_2026-11/`, `phase2_removal/`, `honest_baseline_2026-11/`, `phase4_retrieval/`,
`retrieval_fix_2026-11/`, `heldout_2026-11/`, `llm_latency_2026-11/`, `models/`, `security_2026-11/`, `grounding_2026-11/`,
`retrieval_round2_2026-11/`.

---

## 3. Measured results

### Retrieval: LegalBench-RAG

The benchmark's own scoring code, searching all 714 documents, 95% bootstrap intervals.

**Clean score, 1,209 CUAD queries no earlier run used** (`eval/reports/retrieval_round2_2026-11/`):

| Method | Recall@8 | Precision@8 |
|---|---|---|
| BM25 | 6.2% [4.9, 7.5] | 0.9% |
| Plain vector search | 24.9% [22.6, 27.1] | 3.6% |
| Vector search with document names embedded | 35.3% [33.1, 37.8] | 5.2% |
| Pipeline before D-015 | 35.0% [32.7, 37.5] | 5.1% |
| **JurisGuard pipeline** | **48.5% [46.0, 51.0]** | **6.1%** |
| Document chosen by the user, asked without its name | 73.1% | 9.8% |
| Asked without the name, across all documents | 0.8% | 0.1% |

Paired gain over the pipeline before D-015: +13.5 points [+11.2, +15.5]. ContractNLI and MAUD had no unused queries left;
their held-out final set, scored a second time, gives 84.0% and 28.1%, unchanged by D-015.

**First held-out round, 1,135 queries** (`eval/reports/heldout_2026-11/`): pipeline 39.1% [36.6, 41.6], vector search with
names 36.8%, plain vector search 16.7%, BM25 3.8%; paired +2.3 [1.2, 3.4] over vector search with names. Its first attempt
failed (44.0% against 46.9%) because routing broke at scale.

**Mini set, test split, third scoring** (72 documents, not comparable with 714): pipeline 60.9% [57.4, 64.2].

Every query names its document; these are US contracts.

### German reranking: GerDaLIR

Reordering the official top-100 BM25 candidates on 300 seeded test queries (`eval/reports/retrieval_fix_2026-11/`). BM25
alone scored best (MRR@10 0.345), ahead of bge-m3 (0.284), bge-reranker-v2-m3 (0.244) and ms-marco (0.141). German
questions therefore aren't reordered by the reranker (D-006).

### Speed

Qwen3 8B 100% on the GPU, 10 law questions (`eval/reports/llm_latency_2026-11/`):

| Measure | Value |
|---|---|
| Chat p50 / p95 | 9.1 s / 9.2 s (of which generation 7.8 s) |
| First streamed token | about 0.4 s after retrieval |
| Cache hit | 37 ms |
| First question after restart | about 4.5 s (model kept loaded) |
| Before Phase 5 | p50 28.8 s; 130 s after restart |

### Model choice

Five models that fit 6 GB, same 30 LegalBench questions, judged by a different model (D-010, `eval/reports/models/`).
Qwen3 8B had the best relevancy (0.84), quote accuracy (93%) and German replies (8 of 8). Faithfulness differences of a
few hundredths are noise at this size.

### Security and grounding

From `eval/reports/security_2026-11/README.md` and `grounding_2026-11/`:

| Check | Result |
|---|---|
| BIPIA attacks hidden in uploaded documents, 120 fresh samples | 0.8% followed [0, 2.5], from 19.2% |
| `deepset/prompt-injections` test caught by the input guard | 0% (the classifier caught 36.7% but wasn't deployed, D-013) |
| Legal lookalike questions wrongly blocked | 1 of 20, from 11 |
| ContractNLI: contradicted claims passed by the answer check | 99.1%, so it is a relevance check, not a support check (D-014) |
| Packets to public addresses (API and worker, startup to finished work) | 0 |
| pip-audit | 0 known vulnerabilities in 129 installed packages |
| bandit / OWASP ZAP passive API scan | one reviewed low notice / 114 passed, no failures |

### Regression suite

The project's own 110-case EU suite: 108 of 110 after Phase 6b (106 on the final Phase 6 code); recent runs ranged from 106 to 108
(`eval/reports/retrieval_round2_2026-11/final_code/logical_final.json`). Some questions vary between runs at temperature 0.1. It is a
regression test, not a quality measure: these questions informed design choices.

### Final checks on the current code

After Phase 6b: unit 215 passed, retrieval gate passed, isolation tests 5 of 5 (in the ML container), API end-to-end 48 of
48, Playwright 15 of 15, EU suite 108 of 110, both models 100% on the GPU (`eval/reports/retrieval_round2_2026-11/final_code/`).

---

## 4. Known defects

| Defect | Effect |
|---|---|
| Finding the document depends on the question naming it | No name: 0.8% across all contracts. Named: CUAD 48.5%, against 73.1% with the document chosen |
| Long merger agreements retrieve poorly | MAUD Recall@8 28.1%, and 30.4% with the right document given |
| Keyword search only helps questions citing a provision | Others rely on vector search alone (D-002) |
| About 8% of answerable contract questions are refused | Mini set dev split |
| No retrieval-based refusal for German questions | Out-of-scope German questions rely on the LLM |
| Answers aren't checked for support | A fluent wrong answer on the right topic gets through |
| Hidden instructions in documents can still work | 1 of 120 BIPIA attacks: a reply in French |
| The input guard doesn't stop prompt injection | It only blocks plain attempts at the model's instructions |
| A chosen document is never refused for weak retrieval | Whether the model declines is unmeasured (D-012) |
| An article number without the law's name can hit the wrong statute | "What does Article 12 require?" matched the AI Act. Phase 7 targets this |
| `dlg.py` matches `ILIKE '%Article 6%'` | Also matches Articles 60–69 across every law; its stored edges are never read. Replaced in Phase 7 |
| Gap analysis has no LLM steps | It can't flag a clause that is missing. Phase 8 |
| `SECURITY.md` and compliance templates name runbooks that don't exist | `docs/GDPR_ERASURE.md`, `docs/DISASTER_RECOVERY.md` |

Documents uploaded before document names went into embeddings need re-embedding to benefit.

---

## 5. Architecture

```
┌──────────────────────────────────────────────────────────┐
│ React UI: Research, Matters, Graph, Corpus, Audit, Admin │
│ (Vite :5173, or static /app served by the API)           │
└────────────────────────────┬─────────────────────────────┘
                             │ REST + SSE (/api/v1/chat/stream)
┌────────────────────────────▼─────────────────────────────┐
│ FastAPI: auth, chat, matters, workflows, export, audit   │
│ Middleware: CORS, rate limit, request log, sec. headers  │
│ RAG pipeline (services/rag.py), see §6                   │
└──────┬──────────────────────────────┬────────────────────┘
       │                              │
┌──────▼─────────┐            ┌───────▼────────┐
│ Celery worker  │            │ PostgreSQL 15  │
│ ingest, OCR,   │            │ + pgvector,    │
│ gap, chat jobs │            │ FTS, RLS, audit│
└──────┬─────────┘            └────────────────┘
┌──────▼─────────┐     ┌───────────────────────────────┐
│ Redis: broker, │     │ Ollama on the host, GPU only  │
│ cache, limits  │     │ (OpenRouter possible in dev)  │
└────────────────┘     └───────────────────────────────┘
```

| Process | Entry | Responsibility |
|---|---|---|
| api | `uvicorn main:app` | HTTP, sync and streamed chat, enqueue jobs |
| worker | Celery, `backend/src/worker.py` | Document ingest, gap analysis, async chat, corpus ingest |
| db | Postgres + pgvector | Users, matters, chunks and embeddings, audit, graph |
| cache | Redis | Celery broker, answer cache, rate-limit keys |
| ollama | Host process | Generator and aux model |

---

## 6. How a question is answered

```
question
 → guard: plain attempts at the model's instructions, or over 2,000 characters → 400   (security.py)
 → short-question refusal, then answer cache                                          (query_cache.py)
 → access: documents the user may see; a chosen document limits search to it
 → find a named document: filename rule, else the 3 nearest descriptions (D-015)       (document_routing.py)
 → vector search; keyword search joins only when a provision is cited (D-002)         (vector_store.py)
 → RRF merge, rerank for law search and cited questions (D-004), not for German (D-006)
 → confidence gate, except for a chosen document (D-012)
 → context: five chunks (D-011), marked as data; reply instructions kept out of quotes
 → law questions: dlg.py supplement (to be replaced in Phase 7)
 → generation on Ollama /api/chat, streamed as a draft (D-009)                        (llm_client.py)
 → relevance check: bge-m3 cosine ≥ 0.55 or six shared content words; else quoted text
 → citation check: a cited article must match a retrieved chunk of the same law       (citation_verifier.py)
 → checked answer replaces the draft; cache; audit log
```

Each response carries `answer_mode`: `llm`, `extractive` (quoted text) or `refused`. Each stage is a Prometheus
histogram and, when `OTEL_EXPORTER_OTLP_ENDPOINT` is set, an OpenTelemetry span (D-008). Sync, async and streamed chat
share `_prepare` and `_finish` in `rag.py`.

| Stage | File |
|---|---|
| Orchestration | `backend/src/services/rag.py` |
| Hybrid search SQL | `services/vector_store.py` |
| Embeddings / rerank | `services/embeddings.py`, `services/reranker.py` |
| Document routing | `services/document_routing.py` |
| Law chunking | `services/law_chunking.py` (splits between sentences, drops navigation lines) |
| Contract chunking | `services/advanced_chunking.py` |
| Citation check | `services/citation_verifier.py` |
| LLM | `services/llm_client.py`, `services/ollama_client.py` |
| Gap analysis | `services/agents/gap_analysis.py`, `agents/tools.py` |
| Contract graph | `services/graph_extractor.py`, `graph_persistence.py` (off in the air-gap profile) |

**What it does not do:** check that an answer is supported by its sources; formal legal reasoning; graph retrieval over
the law (yet).

---

## 7. Models and memory layout

| Role | Model | Where |
|---|---|---|
| Generator | `qwen3:8b` (D-010), temperature 0.1, thinking off, `num_ctx` 4096 | GPU, 100% |
| Aux (HyDE, decompose, graph extraction) | `qwen2.5:3b` | GPU; off in the air-gap profile |
| Embeddings | `BAAI/bge-m3`, 1024-dim | CPU |
| Reranker | `cross-encoder/ms-marco-MiniLM-L-6-v2` | CPU |
| RAGAS judge (eval only) | `llama3.1:8b` | GPU, only when nothing else runs |

On 6 GB the LLM gets the whole GPU and embedding and reranking run on the CPU (D-001). The LLM must never spill to CPU or
RAM; `make check-llm-gpu` fails if it does. Start Ollama with:

```bash
LLAMA_ARG_CACHE_RAM=0 OLLAMA_MAX_LOADED_MODELS=1 OLLAMA_NUM_PARALLEL=1 ollama serve
```

`OLLAMA_NUM_GPU=99` forces all layers onto the GPU, and `OLLAMA_KEEP_ALIVE=-1m` keeps the model loaded (D-003). Run one
heavy GPU job at a time: evaluations and serving share the same GPU.

---

## 8. Features

| Feature | Code |
|---|---|
| Research chat (sync, async, SSE) | `routers/chat.py`, `services/rag.py` |
| Threads and feedback | `routers/threads.py` |
| Matters, members, documents | `routers/matters.py` |
| Upload: PDF, DOCX, TXT, MD, EML, MSG, OCR | `services/document_parser.py`, `worker.py` |
| Analyse and compare | `routers/matters.py` |
| Gap analysis (rule-based) | `routers/workflows.py`, `services/agents/` |
| Contract workspace: versions, annotations, DOCX export | `routers/contracts.py` |
| Contract entity graph | `services/graph_*`, `GraphView.jsx` |
| Audit log: hash chain, CSV export, verify | `routers/audit.py`, `services/audit_chain.py` |
| Admin and corpus admin | `routers/admin.py`, `routers/corpus_admin.py` |
| Report export (PDF/DOCX) | `routers/export.py` |
| Branding | `routers/public_config.py`, `BRAND_*` |

---

## 9. Repository layout

```
.github/workflows/   ci, eval, functional-e2e, benchmark-weekly
backend/
  Dockerfile, Dockerfile.gpu, docker-entrypoint.sh
  alembic/versions/  migrations 001–020 plus graph and matters revisions
  requirements-base.txt, -ml.txt, -ci.txt
  src/               main.py, config.py, db.py, worker.py, routers/, services/, middleware/
  tests/             unit and integration tests
frontend/            React 18 + Vite 5; e2e/ holds Playwright tests
eval/
  golden/            project-written regression sets
  legalbench/        LegalBench-RAG harness
  gerdalir/          GerDaLIR reranking harness
  security/          BIPIA, injection, egress capture
  grounding/         ContractNLI check
  reports/           every saved result, by phase
docs/                DECISIONS.md, compliance templates, architecture SVG
scripts/             setup, ingest, eval and bench scripts
experiments/         earlier fine-tuning work, not part of the product
data/                git-ignored: models, corpora, benchmarks, captures
```

---

## 10. Tech stack

| Area | Technology |
|---|---|
| Language | Python 3.12, JavaScript (React 18, Vite 5), SQL, Bash |
| API | FastAPI, uvicorn, pydantic-settings |
| Database | SQLAlchemy async + asyncpg, Alembic, PostgreSQL 15 + pgvector |
| Queue / cache | Celery, Redis 7 |
| Auth | PyJWT (HS256), passlib/bcrypt, slowapi rate limits |
| Documents | pypdf, python-docx, extract-msg, pdf2image, pytesseract, fpdf2 |
| ML | torch 2.14.1 (CPU wheel; cu130 in `Dockerfile.gpu`), transformers 5.22.2, sentence-transformers 6.2.0, tokenizers 0.23.3 |
| Observability | prometheus-client, OpenTelemetry SDK with OTLP HTTP exporter |
| LLM | Ollama on the host |

torch 2.15 for CUDA ships only for CUDA 13.2, which the current driver (13.1) can't run, so 2.14.1 is used; it is past
every fix version pip-audit lists. The library upgrade gave the same embeddings (cosine 1.0) and reranker scores within
2e-6 (`eval/reports/security_2026-11/ml_upgrade_check.json`).

| Image | Role | Host port |
|---|---|---|
| `pgvector/pgvector:pg15` | Postgres | 5433 |
| `redis:7-alpine` | Redis | 6380 |
| API / worker (custom) | FastAPI / Celery | 8002 → 8000 |

---

## 11. Database

PostgreSQL 15 with pgvector. Models in `backend/src/db.py`; migrations in `backend/alembic/versions/`. Never edit an old
migration; add a forward one.

| Table | Purpose |
|---|---|
| `organizations`, `users`, `refresh_tokens` | Tenants, accounts, hashed rotating refresh tokens |
| `document_chunks` | Text, JSONB metadata, `vector(1024)`, full-text index |
| `matters`, `matter_members`, `matter_documents` | Workspaces, per-matter roles, uploads with ingest status |
| `document_versions`, `clause_annotations` | Contract workspace |
| `chat_threads`, `chat_messages`, `answer_feedback` | Chat history and ratings |
| `audit_events` | Actions with `prev_hash` / `row_hash` chain |
| `graph_nodes`, `graph_edges` | Contract entity graph (FK to `matter_documents`, so law needs its own tables) |
| `corpus_sources` | Admin-uploaded corpus files |
| `document_descriptions` | One embedded description per document, for finding it by what a question calls it (D-015) |

Migration 019 removed the enterprise tables; 020 scoped corpus chunks; 021 added `document_descriptions` (one embedded
description per document, written at ingest and deleted with the document, D-015). Law files use fixed document UUIDs in
`backend/src/ingest_law.py` (`gdpr_en.txt` …110001, `bgb_en.txt` …110002, `bdsg_de.txt` …110003, `eu_ai_act_en.txt`
…110004). **Law chunks indexed: 4,129** (re-chunked in Phase 6, from 4,172).

---

## 12. API

Base `http://localhost:8002`. OpenAPI at `/docs` when `EXPOSE_OPENAPI=true`.

| Area | Endpoints |
|---|---|
| Public | `GET /health`, `GET /api/v1/config/branding` |
| Metrics | `GET /metrics`: open in development; in production needs `Authorization: Bearer $METRICS_TOKEN`, 404 otherwise |
| Status | `GET /api/v1/status` (JWT) |
| Auth `/api/v1/auth` | `POST /register` (if `REGISTRATION_OPEN`), `POST /login`, `POST /refresh`, `GET /me` |
| Chat `/api/v1/chat` | `POST /` sync, `POST /async` + `GET /jobs/{id}`, `POST /stream` SSE (draft, then checked answer) |
| Threads | `GET/POST /api/v1/threads`, `GET /threads/{id}/messages`, `POST /api/v1/feedback` |
| Matters `/api/v1/matters` | CRUD, members, documents (upload, bulk, status, delete), graph, analyse, compare |
| Contracts | Workspace, versions, annotations, `export/docx`, under matter documents |
| Workflows | `POST /api/v1/matters/{id}/workflows/gap-analysis`, `GET /api/v1/workflows/gap-analysis/{job_id}` |
| Corpus | `GET /api/v1/corpus/stats`, `POST /corpus/dlg/bootstrap`, `POST /corpus/ingest-law` |
| Admin corpus | `/api/v1/admin/corpus`: sources, upload, ingest |
| Audit (org_admin+) | list, export, verify |
| Admin (org_admin+) | run-eval, eval-status, users, roles, org settings, revoke sessions |
| Export | analyse report, compare report, audit |

Every response carries `X-Content-Type-Options: nosniff`, `Cross-Origin-Resource-Policy: same-origin`,
`Referrer-Policy: no-referrer` and `X-Frame-Options: DENY` (`middleware/security_headers.py`, safe for streaming).
Cross-organisation access returns 404, not 403.

---

## 13. Frontend

`frontend/`, React 18 + Vite 5, no router library (view state in `App.jsx`), API client `src/lib/api.js`, custom CSS.
Components: `LoginPage`, `Sidebar`, `ChatView` (streams answers), `SourcePanel`, `MattersView`, `ContractEditor`,
`GraphView`, `CorpusView`, `AuditView`, `AdminView`, `SystemView`, `HelpView`, `ExportModal`, `Toast`, `Icons`.

| Mode | Command | URL |
|---|---|---|
| Dev | `make ui-dev` | http://localhost:5173 |
| Built | `make ui-build`, `SERVE_UI_FROM_API=true` | http://localhost:8002/app |

Env: `VITE_API_URL`, `VITE_DEV_EMAIL` / `VITE_DEV_PASSWORD`, `VITE_PORT`, `VITE_DEBUG_API`.

---

## 14. Workers

`backend/src/worker.py`, broker Redis.

| Task | Trigger | Work |
|---|---|---|
| `process_document_task` | Upload | Parse (OCR if sparse) → chunk → embed with document name → optional graph → status |
| `gap_analysis_task` | Gap workflow | Rule-based checks, at most 12 tool calls and 5 obligations |
| `chat_task` | Async chat | Same pipeline as sync chat |
| `ingest_corpus_task` | Corpus admin | Ingest an uploaded law source |

A failed enqueue is logged and reported; earlier, bulk upload and corpus ingest reported success without queuing work.

---

## 15. Auth and security

- JWT HS256 access tokens (15 min) and hashed refresh tokens (7 days); bcrypt passwords.
- Org roles `member` → `matter_lead` → `org_admin` → `owner`; matter roles `viewer` → `editor` → `owner`;
  confidentiality tiers `internal` / `restricted` / `privileged` (`services/access_control.py`). RLS on by default.
- Dev master user (`DEV_MASTER_ENABLED`) for local eval and E2E only.

`validate_settings()` (`services/config_security.py`) stops a production start when: dev master is on, registration is
open, OpenAPI is exposed, the secret is under 32 characters or a known default, an `OPENROUTER_API_KEY` is set with
`LLM_PROVIDER=ollama`, or the OTLP endpoint is not on the local network.

| Control | Where |
|---|---|
| Input guard (narrow, D-013) | `services/security.py` |
| Document text marked as data | `services/rag.py`, `llm_client.py` |
| Citation check | `services/citation_verifier.py` |
| Rate limits | slowapi + Redis |
| Upload checks | `services/upload_security.py` |
| Security headers | `middleware/security_headers.py` |
| Offline models | HF offline flags, no Hub fallback, remote code off |
| Audit chain | `services/audit_chain.py`; run `GET /api/v1/audit/verify` after upgrades |

The egress check is `eval/security/egress_capture.sh api|worker`. No pen test has been done. Compliance files in
`docs/compliance/` are templates, not certification.

---

## 16. Configuration

Settings live in `backend/src/config.py`. Templates: `.env.example` (dev) and `.env.airgap.example` (production, local).

| Env var | Default | Air-gap template |
|---|---|---|
| `ENVIRONMENT` | `development` | `production` |
| `LLM_PROVIDER` / `LLM_AUX_PROVIDER` | `openrouter` / `ollama` | `ollama` / `ollama` |
| `OLLAMA_BASE_URL` | `http://localhost:11434` | `http://host.docker.internal:11434` |
| `OLLAMA_MODEL` / `OLLAMA_AUX_MODEL` | `qwen3:8b` / `qwen2.5:0.5b` | `qwen3:8b` / `qwen2.5:3b` |
| `OLLAMA_NUM_GPU` / `OLLAMA_NUM_CTX` / `OLLAMA_KEEP_ALIVE` | unset / 4096 / `-1m` | 99 / 4096 / default |
| `EMBEDDING_DEVICE` / `RERANKER_DEVICE` | `auto` | `cpu` |
| `AIRGAP_LATENCY_PROFILE` | on when provider is ollama | `true` |
| `HYDE_ENABLED`, `ADAPTIVE_HYDE_ENABLED`, `CRAG_RETRY_ENABLED` | false, true, true | all false |
| `GRAPH_EXTRACTION_ENABLED` | true | false |
| `HYBRID_SEARCH_ENABLED`, `CITATION_VERIFY_ENABLED`, `QUERY_CACHE_ENABLED`, `RLS_ENABLED` | true | true |
| `SEMANTIC_CONTEXT_MIN_COSINE` / `RAG_MIN_RERANK_SCORE` | 0.55 / -2.0 | |
| `REGISTRATION_OPEN`, `EXPOSE_OPENAPI`, `DEV_MASTER_ENABLED` | true, true, false | false |
| `AUTH_SECRET_KEY` | placeholder | set 32+ characters |
| `METRICS_TOKEN` | empty | set to expose `/metrics` |
| `TRACING_ENABLED` / `OTEL_EXPORTER_OTLP_ENDPOINT` | false / unset | local collector only |

Fixed in code: `rag_top_k` 20, `rag_rerank_k` 5, `rag_rrf_k` 60, `embedding_dim` 1024, `chat_history_turns` 3.

Under Docker Desktop on WSL, `host.docker.internal` reaches Windows; if Ollama runs inside WSL, set `OLLAMA_BASE_URL`
to the address from `hostname -I` (it can change on reboot).

---

## 17. Data and storage

`data/` is git-ignored.

| Path | Contents |
|---|---|
| `data/models/bge-m3/`, `data/models/reranker/` | Model weights |
| `data/raw/law_corpus/` | The four law texts |
| `data/benchmarks/` | LegalBench-RAG, GerDaLIR, BIPIA, ContractNLI scores, egress captures |
| `data/airgap-bundle/` | Offline deploy bundle |

Docker volumes: `postgres_data`, `uploads_data`, `hf_cache`.

Golden sets in `eval/golden/` (project-written, regression only): `law_qa` 50, `contract_qa` 20, `injection` 15,
`injection_benign` 20, `rbac` 10.

---

## 18. Setup and operations

Needs Docker, Python 3.12, Node 20, and for local generation an NVIDIA GPU with Ollama on the host.

```bash
git clone https://github.com/hamdan-ishfaq/juris-slm.git && cd juris-slm
cp .env.example .env          # set AUTH_SECRET_KEY; .env.airgap.example for local-only
ollama pull qwen3:8b && ollama pull qwen2.5:3b
make models && make download-law
make up && make migrate
make check-llm-gpu            # fails unless the LLM is fully on the GPU
make ingest-law-docker
make ui-dev                   # http://localhost:5173
```

| Target | Action |
|---|---|
| `up`, `down`, `rebuild`, `logs`, `ps` | Compose lifecycle (`up-gpu`, `gpu-build`, `gpu-up`, `verify-gpu` for CUDA) |
| `migrate`, `models`, `verify`, `check-llm-gpu` | Schema, weights, asset check, GPU check |
| `download-law`, `ingest-law`, `ingest-law-docker` | Law corpus |
| `test`, `test-unit`, `test-integration`, `e2e`, `ui-e2e` | Tests |
| `eval-offline`, `eval-logical`, `eval-proxy`, `eval-native`, `eval-latency` | Evaluations |
| `retrieval-gate`, `bench` | Retrieval check on fixtures; LegalBench mini table |
| `eval-ollama-full`, `eval-full-local`, `eval-3x`, `brutal-gate` | Longer runs |
| `airgap-bundle`, `airgap-eval` | Offline packaging |
| `ui-dev`, `ui-dev-stop`, `ui-dev-restart`, `ui-build` | Frontend |
| `regulatory-diff`, `generate-golden`, `fix-upload-perms` | Utilities |

Deploy modes: dev Compose; production with `-f docker-compose.prod.yml`; air-gap bundle; UI served from the API.

---

## 19. Testing

| Suite | Command | Last result |
|---|---|---|
| Unit | `make test-unit` | 215 passed |
| Integration (isolation, needs the ML packages) | run inside the API image | 5 of 5 |
| API end-to-end | `make e2e` (`CI_SKIP_LLM=1` on CI) | 48 of 48 |
| Browser | `make ui-e2e` | 15 of 15 |
| EU regression suite | `make eval-logical` | 108 of 110 |

On the host, the two isolation tests fail only because `sentence_transformers` isn't installed there; run them in the
container. Playwright on WSL may need `LD_LIBRARY_PATH` pointing at extracted browser libraries such as `libnspr4`.

---

## 20. Evaluation and benchmarks

Rules followed: tune on dev only; score test once and don't read its failures; pin commit, dataset, model and config;
keep failed runs; bootstrap 95% intervals; use the benchmark's own scoring or state the adaptation.

| Harness | Path |
|---|---|
| LegalBench-RAG (retrieval) | `eval/legalbench/`, `make bench` |
| GerDaLIR (German reranking) | `eval/gerdalir/gerdalir.py` |
| BIPIA (document injection) | `eval/security/bipia_attack.py` |
| Direct injection | `eval/security/injection.py` |
| ContractNLI (answer check) | `eval/grounding/contractnli.py` |
| Egress | `eval/security/egress_capture.sh` |
| RAGAS (secondary, local judge) | `make eval-native` |
| Regression suite | `scripts/run_logical_eval.py` |
| Latency | `scripts/run_latency_bench.py` |

The June 2026 files in `eval/reports/` (`ollama_eval_summary_*`, `latency_*`, `brutal_gate_*`) predate the rework and
are kept as history only; their 91.8% and 2.7-minute figures don't describe the current system.

---

## 21. CI

| Workflow | Trigger | Runs |
|---|---|---|
| `ci.yml` | push, PR | Unit tests, functional E2E without the LLM, offline regression ×3, frontend build |
| `eval.yml` | push, PR, Mondays 03:00 UTC | Security and golden tests, retrieval gate on fixtures, production config guard, latency, E2E |
| `functional-e2e.yml` | push, PR | Unit and functional E2E |
| `benchmark-weekly.yml` | Mondays 04:00 UTC | `make bench` on CPU, table as annotations and artifact |

CI has no GPU, so LLM answers aren't tested there; the retrieval gate is the quality check that can fail a PR.

---

## 22. Decisions log

Full entries in `docs/DECISIONS.md` (append-only).

| ID | Decision |
|---|---|
| D-001 | LLM takes the GPU; embedding and reranking on CPU |
| D-002 | Keyword search only joins when a question cites a provision |
| D-003 | Keep the LLM's RAM use small while it runs on the GPU |
| D-004 | Reorder by reranker for law search and cited questions |
| D-005 | Search a document first when the question names it |
| D-006 | No English reranker on German; trust a retrieved citation |
| D-007 | Tighter document routing after it failed at scale |
| D-008 | OpenTelemetry tracing, local collector only |
| D-009 | Stream a draft, then the checked answer |
| D-010 | Qwen3 8B as the generator |
| D-011 | Five chunks of context |
| D-012 | No retrieval-score refusal for a chosen document |
| D-013 | Narrow input guard; injection classifier not deployed |
| D-014 | No NLI gate yet; the current check is a relevance check |
| D-015 | When the filename rule fails, search the 3 documents with the nearest descriptions |

---

## 23. Remaining plan

**Phase 7, citation graph** (`feature/citation-graph`): law node and edge tables via migration, parsed from the text by
rules (`Art. 6`, `§ 26 BDSG`, defined terms), with parser precision and recall on a hand-checked sample. Replaces
`dlg.py`. 1–2 hop traversal, reranked, hard cap on added text, used only for linked-provision questions; added text
shown in sources with its path. Measured with and without the graph on LegalBench and GraphRAG-Bench (non-legal).
Done when one real question is fixed by the graph and a benchmark table is published either way.

**Phase 8, gap-analysis agent**: score the current rule-based version on CUAD first; then bounded, schema-validated LLM
steps with absent-clause detection, claim-level citations, an audit log and a real call budget; compared with the
rule-based version and a plain-LLM baseline. Cut if it doesn't beat them.

**Phase 9, MCP server**: read-only `search_law`, `get_article`, `check_citation`, hashed bearer token, audit logged.

**Phase 10**: `docs/DESIGN.md`, build story, results tables, and a clean-clone run with outbound network blocked.

Not planned: fine-tuning, Kubernetes, voice, Neo4j, an LLM-extracted law graph. Asked separately: repo rename, an AWS
GPU session, a video.

---

## 24. Conventions

- Branch from `master`: `feature/`, `fix/`, `chore/`, `docs/`. Each finished phase is merged to `master` with the README
  updated.
- Small commits, imperative subject under 72 characters, body only to explain why.
- Decisions that are costly to reverse go in `docs/DECISIONS.md`; amend, don't rewrite.
- Never edit an old migration. Settings use `SCREAMING_SNAKE_CASE` env names via `validation_alias`.
- Numbers in docs must trace to a saved report. Failed runs are kept.
- Git-ignored: `data/`, `.env`, model files, uploads, tool config.

---

## 25. Day-one checklist

1. Read `README.md`, then this file, then `docs/DECISIONS.md`.
2. Set up as in §18 and confirm `make check-llm-gpu` passes.
3. Log in as dev master and ask one law question; watch the draft turn into the checked answer.
4. Run `make test-unit` and `CI_SKIP_LLM=1 make e2e`.
5. Read `services/rag.py` (`_prepare`, `_finish`) once end to end.
6. Before changing retrieval or prompts, run `make bench` and `make eval-logical` for a before figure.

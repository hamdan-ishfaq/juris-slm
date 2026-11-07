# JurisGuard V2 — Complete Project Handoff

**Canonical single handoff document for the entire project.**  
All other docs (`README.md`, `SECURITY.md`, compliance templates) are summaries or specialty runbooks that point here for full context.

| Field | Value |
|-------|--------|
| **Product** | JurisGuard V2 |
| **Repo** | https://github.com/hamdan-ishfaq/juris-slm |
| **Active code** | Repo root (legacy V1 removed) |
| **App version** | `0.5.0` (`backend/src/main.py`) |
| **Status** | In development, not in production use |
| **Default branch tip** | `master` (also tracks `main`) |
| **Working directory for all commands** | Repo root |
| **Hardware validated** | WSL2 · RTX 4050 6GB · CUDA embed/rerank · Ollama on host |

---

## Table of contents

1. [Executive summary](#1-executive-summary)
2. [Problem, buyers, and product value](#2-problem-buyers-and-product-value)
3. [Repository layout](#3-repository-layout)
4. [Tech stack and versions](#4-tech-stack-and-versions)
5. [Architecture](#5-architecture)
6. [Model tiers (T0–T3)](#6-model-tiers-t0t3)
7. [RAG pipeline (deep dive)](#7-rag-pipeline-deep-dive)
8. [Core features](#8-core-features)
9. [Database schema](#9-database-schema)
10. [API surface (complete)](#10-api-surface-complete)
11. [Frontend](#11-frontend)
12. [Workers and async jobs](#12-workers-and-async-jobs)
13. [Auth, RBAC, and security](#13-auth-rbac-and-security)
14. [Configuration and environment variables](#14-configuration-and-environment-variables)
15. [Data, corpora, and storage](#15-data-corpora-and-storage)
16. [Setup, run, and operations](#16-setup-run-and-operations)
17. [Makefile targets](#17-makefile-targets)
18. [Scripts catalog](#18-scripts-catalog)
19. [Evaluation and benchmarks](#19-evaluation-and-benchmarks)
20. [Testing](#20-testing)
21. [CI/CD](#21-cicd)
22. [Deployment modes](#22-deployment-modes)
23. [Training / fine-tune (optional)](#23-training--fine-tune-optional)
24. [Compliance and security docs](#24-compliance-and-security-docs)
25. [Known limitations and backlog](#25-known-limitations-and-backlog)
26. [Development history (phases)](#26-development-history-phases)
27. [File map (critical paths)](#27-file-map-critical-paths)
28. [Conventions](#28-conventions)
29. [Day-one checklist for a new engineer](#29-day-one-checklist-for-a-new-engineer)

---

## 1. Executive summary

**JurisGuard V2** is a **self-hosted, on-prem legal intelligence platform** for EU privacy and in-house legal teams. It provides:

- **Grounded research chat** over EU law corpora (GDPR, BGB, BDSG, EU AI Act) with citations
- **Matter-scoped contract Q&A** — upload deals, analyze, compare against the law baseline
- **Gap analysis** — bounded async regulatory gap reports for DPO workflows
- **Access controls** — org isolation, RBAC, row-level security, SHA-256 hash-chained audit
- **Air-gap mode** — no outbound LLM calls when `LLM_PROVIDER=ollama`

**Core design idea:** product value is the **hybrid RAG pipeline** (retrieve → RRF → rerank → augment → verify → fallback), not raw LLM IQ.

**Default URLs (dev):**

| Service | URL |
|---------|-----|
| API | http://localhost:8002 |
| OpenAPI | http://localhost:8002/docs |
| UI (Vite) | http://localhost:5173 |
| UI (built, from API) | http://localhost:8002/app |

---

## 2. Problem, buyers, and product value

### Problem

EU legal/privacy teams cannot safely use generic cloud AI on client work because of:

- **Data residency** (NDA / DPIA constraints)
- **Hallucination risk** on legal citations
- **Siloed knowledge** across deals and statutes
- **No audit trail** for regulators / DPOs

### Buyers and deliverables

| Buyer | Deliverable |
|-------|-------------|
| DPO | Grounded research + gap analysis report |
| In-house counsel | Matter upload, analyze, compare, export |
| CISO / IT | Org isolation, hash-chained audit |
| Regulated SME | Full air-gap: Ollama + local embeddings only |

### Architecture decisions (why)

| Decision | Rationale |
|----------|-----------|
| pgvector inside Postgres | One DB for users, vectors, audit — air-gap friendly |
| Hybrid search (vector + BM25) | Legal queries use exact article numbers; keyword leg is essential |
| Model tiers T0–T3 | Retrieval always local; only T2 generation swaps cloud ↔ on-prem |
| Celery for ingest | PDF/OCR/chunking takes minutes; API must not block |
| Bounded gap agent | Fixed tool chain (max 12 LLM calls) — predictable cost/latency |
| Hash-chained audit | Tamper-evident log for DPO/regulator story |

---

## 3. Repository layout

```
juris-slm/                          # Git root
├── README.md                       # Architecture, benchmarks, quickstart
├── .gitignore / .gitattributes
├── .github/workflows/
│   ├── ci.yml                      # Unit + E2E + offline eval + frontend build
│   ├── eval.yml                    # Eval harness + weekly cron
│   └── functional-e2e.yml          # Functional E2E workflow
├── COMPLETE_PROJECT_HANDOFF.md # ★ This document (canonical)
├── SECURITY.md                 # Pen-test scope, hardening checklist
├── Makefile                    # Primary ops interface
├── .env.example                # Dev profile
├── .env.airgap.example         # Production air-gap profile
├── docker-compose.yml          # db, cache, api, worker (+ ollama profile)
├── docker-compose.prod.yml     # Production overrides
├── docker-compose.gpu.yml      # CUDA embed/rerank
├── backend/
│   ├── Dockerfile / Dockerfile.gpu
│   ├── docker-entrypoint.sh
│   ├── alembic.ini + alembic/versions/   # 20 migration files
│   ├── requirements-base.txt / -ml.txt / -ci.txt / requirements.txt
│   ├── src/                    # FastAPI app, services, routers, worker
│   └── tests/                  # ~44 test modules
├── frontend/
│   ├── package.json            # React 18 + Vite 5
│   ├── src/                    # SPA components
│   └── e2e/                    # Playwright
├── eval/
│   ├── golden/                 # JSONL golden datasets (95 cases)
│   ├── fixtures/               # Contract text fixtures
│   ├── reports/                # Benchmark JSON outputs
│   └── baseline.json           # Dev RAGAS faithfulness baseline (0.87)
├── docs/
│   ├── HANDOFF.md              # Short pointer → this file
│   ├── jurisguard_v2_architecture.svg
│   └── compliance/             # Control matrix, IR, retention
├── scripts/                    # ~58 ops / eval / training scripts
├── deploy/Modelfile.example    # Custom Ollama GGUF slot
├── experiments/finetune/        # Fine-tuning work, not part of the product
└── data/                       # GITIGNORED — models, law corpus, uploads
```



---

## 4. Tech stack and versions

### Languages

| Language | Use |
|----------|-----|
| Python **3.12** | Backend, Celery, scripts, eval |
| JavaScript / JSX | React SPA |
| SQL | Alembic migrations, hybrid search |
| Bash / PowerShell | Setup, CI, air-gap bundles |

### Backend

| Component | Technology | Constraint |
|-----------|------------|------------|
| API | FastAPI | `>=0.115.0,<0.137.0` |
| ASGI | uvicorn | `>=0.30.0,<0.49.0` |
| Settings | pydantic-settings | `>=2.4.0,<3.0.0` |
| ORM | SQLAlchemy async | `>=2.0.30,<2.1.0` |
| DB driver | asyncpg | `>=0.29.0,<0.32.0` |
| Migrations | Alembic | `>=1.13.0,<2.0.0` |
| Cache / queue | Redis + Celery | redis `>=5`, celery `>=5.3` |
| Auth | python-jose + passlib/bcrypt | JWT HS256 |
| Rate limit | slowapi | Redis-backed |
| HTTP client | httpx | LLM |
| Docs | pypdf, python-docx, extract-msg, pdf2image, pytesseract | Parse + OCR |
| Export | fpdf2, python-docx | PDF/DOCX reports |
| Metrics | prometheus-client | `/metrics` |

### ML (always local for T0)

| Package | Pin |
|---------|-----|
| torch | `2.6.0` (CPU default Docker; CUDA via `Dockerfile.gpu`) |
| sentence-transformers | `3.4.1` |
| transformers | `4.49.0` |
| tokenizers | `0.21.4` |

Models on disk (not pip):

- Embeddings: `BAAI/bge-m3` → `data/models/bge-m3` (~2.2 GB, **1024-dim**)
- Rerank: `cross-encoder/ms-marco-MiniLM-L-6-v2` → `data/models/reranker` (~84 MB)

### Frontend

| Package | Version |
|---------|---------|
| react / react-dom | `^18.3.1` |
| vite | `^5.4.2` |
| @playwright/test | `^1.49.0` |

**No Tailwind / UI kit** — custom CSS in `frontend/src/styles.css`.

### Infrastructure images

| Image | Role | Host port (dev) |
|-------|------|-----------------|
| `pgvector/pgvector:pg15` | Postgres + vectors | **5433** |
| `redis:7-alpine` | Broker + cache + rate limits | **6380** |
| `ollama/ollama:latest` | Optional compose profile | **11434** |
| Custom API/worker | FastAPI + Celery | **8002** → container 8000 |

---

## 5. Architecture

```
┌─────────────────────────────────────────────────────────────┐
│  React UI — Research, Matters, Graph, Audit, Admin, Help    │
│  (Vite :5173 or static /app from API)                       │
└───────────────────────────┬─────────────────────────────────┘
                            │ REST + SSE (/api/v1/chat/stream)
┌───────────────────────────▼─────────────────────────────────┐
│  FastAPI (main.py v0.5.0)                                   │
│  Auth · chat · matters · workflows · export · audit · admin │
│  Middleware: CORS, SlowAPI rate limit, request log          │
├─────────────────────────────────────────────────────────────┤
│  RAG (services/rag.py)                                      │
│  guard → cache → embed → hybrid → RRF → rerank              │
│  → DLG → T2 LLM → citation verify → T3 fallback → audit     │
└───────┬───────────────────────────────┬─────────────────────┘
        │                               │
┌───────▼────────┐              ┌───────▼────────┐
│ Celery worker  │              │ PostgreSQL 15  │
│ ingest, OCR,   │              │ + pgvector     │
│ gap, chat jobs │              │ + FTS / audit  │
└───────┬────────┘              └────────────────┘
        │
┌───────▼────────┐     ┌─────────────────┐
│ Redis          │     │ Ollama (host)   │
│ broker + cache │     │ or OpenRouter   │
└────────────────┘     └─────────────────┘
```

### Process boundaries

| Process | Entry | Responsibility |
|---------|-------|----------------|
| **api** | `uvicorn main:app` | HTTP, sync chat path, enqueue jobs |
| **worker** | Celery via `worker.py` | Document ingest, gap analysis, async chat, corpus ingest |
| **db** | Postgres | Users, matters, chunks+embeddings, audit, graph |
| **cache** | Redis | Celery broker, query cache, rate-limit keys |
| **ollama** | Host or compose profile | T1 aux + T2 generation when air-gapped |
| **ui** | Vite or static mount | SPA |

### Integration points

- **UI → API:** `frontend/src/lib/api.js` — JWT bearer; Vite proxies to `:8002`
- **API → Worker:** Celery tasks enqueued from upload / workflows / async chat
- **Worker → DB:** SQLAlchemy (sync paths in Celery); optional RLS via `services/rls.py`
- **RAG → Models:** Local bge-m3/reranker; LLM via `llm_client.py` / `ollama_client.py`
- **Audit:** SHA-256 hash chain on `audit_events`; verify via `GET /api/v1/audit/verify`

---

## 6. Model tiers (T0–T3)

| Tier | Role | Component | Always local? |
|------|------|-----------|---------------|
| **T0** | Retrieval | bge-m3 + BM25 + RRF + ms-marco cross-encoder | **Yes** |
| **T1** | Aux | HyDE, query decompose, graph extract — Ollama `qwen2.5:3b` | Yes (Ollama) |
| **T2** | Generation | Air-gap: `mistral:7b-instruct-v0.3-q4_K_M` · Dev: OpenRouter `microsoft/phi-4-mini-instruct` | Swappable |
| **T3** | Safety fallback | Extractive answer from best chunk + bge-m3 cosine grounding | **Yes** |

**Air-gap latency profile** (`AIRGAP_LATENCY_PROFILE=true` or auto when `LLM_PROVIDER=ollama`):

- Disables adaptive HyDE and CRAG retry
- Typically disables graph extraction (`GRAPH_EXTRACTION_ENABLED=false`)
- Keeps hybrid search + rerank + citation verify

---

## 7. RAG pipeline (deep dive)

### End-to-end chat flow

```
Query
  → prompt-injection guard (security.py)
  → Redis query cache (optional)
  → embed query (+ optional HyDE / legal expansion on T1)
  → hybrid retrieve: pgvector cosine + BM25 FTS
  → RRF merge (k=60 default)
  → cross-encoder rerank (top 5; floor RAG_MIN_RERANK_SCORE)
  → DLG structural supplement for law (dlg.py — curated GDPR edges)
  → T2 grounded generation (llm_client.py SYSTEM_PROMPT)
  → citation verify (label in sources) + semantic cosine check
  → T3 extractive fallback if grounding fails
  → audit hash chain
  → response (+ sources)
```

### Key implementation files

| Stage | File |
|-------|------|
| Orchestration | `backend/src/services/rag.py` |
| Hybrid + BM25 + filters | `backend/src/services/vector_store.py` |
| Embeddings | `backend/src/services/embeddings.py` |
| Rerank | `backend/src/services/reranker.py` |
| RRF | `backend/src/services/rrf.py` |
| HyDE | `backend/src/services/hyde.py` |
| Query expansion / CRAG | `backend/src/services/query_enhance.py` |
| Query decompose | `backend/src/services/query_decompose.py` |
| Contextual retrieval | `backend/src/services/contextual_retrieval.py` |
| Law chunking | `backend/src/services/law_chunking.py` |
| Contract chunking | `backend/src/services/advanced_chunking.py` |
| DLG | `backend/src/services/dlg.py` |
| Citation verify | `backend/src/services/citation_verifier.py` |
| LLM routing | `backend/src/services/llm_client.py`, `ollama_client.py` |
| Gap agent | `backend/src/services/agents/gap_analysis.py` |
| Graph extract | `backend/src/services/graph_extractor.py`, `graph_persistence.py` |

### Retrieval defaults (`config.py`)

| Setting | Default |
|---------|---------|
| `rag_top_k` | 20 |
| `rag_rerank_k` | 5 |
| `rag_max_context_chars` | 6000 |
| `rag_rrf_k` | 60 |
| `embedding_dim` | 1024 |
| `semantic_context_min_cosine` | 0.55 |
| `rag_min_query_words` | 3 |
| `chat_history_turns` | 3 |

### What the pipeline does **not** do

- Formal legal inference / entailment proving
- Rule-based “IF Art. 6 THEN lawful” chains
- NLI-based citation verification (label + cosine only)
- Full graph RAG over the entire law corpus (DLG is a small curated edge list)

**“Logical eval”** = automated substring/regression harness — not a claim of formal reasoning.

---

## 8. Core features

| Feature | Purpose | Primary code |
|---------|---------|--------------|
| Grounded research chat | Law corpus Q&A with sources; sync / async / SSE | `routers/chat.py`, `services/rag.py` |
| Chat threads + feedback | Persist history; thumbs / corrections | `routers/threads.py` |
| Matters | Per-deal workspace + members | `routers/matters.py` |
| Document upload | PDF/DOCX/TXT/MD/EML/MSG + OCR | `document_parser.py`, `worker.py` |
| Analyze / compare | Matter-scoped Q&A vs law baseline | `matters.py` analyze/compare |
| Compare clause | Clause-level comparison | `matters.py` compare-clause |
| Gap analysis | Async DPO gap report (≤12 LLM calls) | `workflows.py`, `agents/gap_analysis.py` |
| Contract workspace | Versions, annotations, DOCX export | `routers/contracts.py` |
| Knowledge graph | Contract entities/edges on ingest | `graph_*`, Graph UI |
| Audit log | SHA-256 chain, CSV export, verify, seal | `routers/audit.py` |
| Admin | Users, org, eval | `routers/admin.py` |
| Corpus admin | Upload extra law sources | `routers/corpus_admin.py` |
| Export reports | Analyze/compare/audit PDF/DOCX | `routers/export.py` |
| White-label | Brand name/color/logo | `public_config.py`, `BRAND_*` |

---

## 9. Database schema

**Engine:** PostgreSQL 15 + `pgvector`  
**ORM models:** `backend/src/db.py`  
**Migrations:** `backend/alembic/versions/` (001–018 + graph + matters)

### Tables (summary)

| Table | Purpose |
|-------|---------|
| `organizations` | Tenant; slug; JSONB settings |
| `users` | Email, bcrypt hash, org role |
| `refresh_tokens` | Rotating refresh tokens (hashed) |
| `document_chunks` | Content + JSONB metadata + **vector(1024)** + FTS |
| `matters` | Deal/workspace |
| `matter_members` | Per-matter RBAC (viewer/editor/owner) |
| `matter_documents` | Uploads; confidentiality; ingest_status |
| `document_versions` | Contract editor versions + clauses JSON |
| `clause_annotations` | Comments on clauses |
| `chat_threads` / `chat_messages` | Chat history + sources |
| `answer_feedback` | User ratings/corrections |
| `audit_events` | Actions + `prev_hash` / `row_hash` chain |
| `graph_nodes` / `graph_edges` | Contract entity graph |
| `corpus_sources` | Admin-uploaded corpus files |

### Migration order (conceptual)

1. Initial pgvector  
2. Users schema  
3. Document chunks  
4. RBAC  
5. Hybrid search (FTS)  
6. Chat feedback  
7. Org isolation  
8. Legal holds  
9. Org hardening  
10. RLS policies  
11. SSO/SCIM  
12. Audit WORM  
13. Contract workspace  
14. Refresh tokens  
15. Corpus sources  
16. Clause library  
17. Matter ingest status  
18. Matter deadlines  
19. Removal of SSO, SCIM, WORM, legal hold, clause library, deadlines  
+ Graph tables, matters/documents (revision hashes)

### Law corpus fixed document UUIDs (`ingest_law.py`)

| File | Source | UUID suffix |
|------|--------|-------------|
| `gdpr_en.txt` | gdpr | `...110001` |
| `bgb_en.txt` | bgb | `...110002` |
| `bdsg_de.txt` | bdsg | `...110003` |
| `eu_ai_act_en.txt` | eu_ai_act | `...110004` |

**Indexed law chunks (Jun 2026):** **1,957**

---

## 10. API surface (complete)

**Base:** `http://localhost:8002`  
**OpenAPI:** `/docs` when `EXPOSE_OPENAPI=true`  
**Version string:** `0.5.0`

### Public / health

| Method | Path | Auth |
|--------|------|------|
| GET | `/health` | None |
| GET | `/metrics` | None (Prometheus) |
| GET | `/api/v1/config/branding` | None |
| GET | `/api/v1/status` | JWT (detail for admins) |

### Auth — `/api/v1/auth`

| Method | Path | Notes |
|--------|------|-------|
| POST | `/register` | Rate limit ~15/min; gated by `REGISTRATION_OPEN` |
| POST | `/login` | ~5/min |
| POST | `/refresh` | ~30/min |
| GET | `/me` | JWT |

### Chat — `/api/v1/chat` (JWT, ~10/min)

| Method | Path | Notes |
|--------|------|-------|
| POST | `/` | Sync RAG |
| POST | `/async` | Enqueue `chat_task` |
| GET | `/jobs/{job_id}` | Poll async |
| POST | `/stream` | SSE |

### Threads — `/api/v1`

`GET/POST /threads`, `GET /threads/{id}/messages`, `POST /feedback`

### Matters — `/api/v1/matters`

- CRUD: `POST/GET ""`, `GET/DELETE /{id}`
- Members: `POST /{id}/members`, `DELETE /{id}/members/{user_id}`
- Documents: list/upload/status/delete/bulk/bulk-files
- Graph: entities, edges, extract
- Analyze / compare / compare-clause

### Contracts workspace — under matters documents

workspace GET/PUT, versions, annotations, `export/docx`

### Workflows

`POST /api/v1/matters/{id}/workflows/gap-analysis` (~5/hr)  
`GET /api/v1/workflows/gap-analysis/{job_id}`

### Corpus

`GET /api/v1/corpus/stats`  
`POST /api/v1/corpus/dlg/bootstrap`  
`POST /api/v1/corpus/ingest-law`

### Admin corpus — `/api/v1/admin/corpus`

sources list, upload, ingest by id

### Audit — `/api/v1/audit` (org_admin+)

list, export, verify, seal

### Admin — `/api/v1/admin` (org_admin+)

run-eval, eval-status, users CRUD/role, org get/patch, revoke sessions

### Export — `/api/v1/export`

analyze-report, compare-report, audit

---

## 11. Frontend

**Path:** `frontend/`  
**Stack:** React 18 + Vite 5 (no router library — view state in `App.jsx`)  
**API client:** `src/lib/api.js`  
**Styles:** `src/styles.css`

### Views / components

| Component | Role |
|-----------|------|
| `LoginPage.jsx` | Login/register |
| `Sidebar.jsx` | Nav |
| `ChatView.jsx` | Research chat |
| `SourcePanel.jsx` | Citation panel |
| `MattersView.jsx` | Matters + documents |
| `ContractEditor.jsx` | Workspace editor |
| `GraphView.jsx` | Entity graph |
| `CorpusView.jsx` | Corpus stats / ingest |
| `AuditView.jsx` | Audit log |
| `AdminView.jsx` | Admin |
| `SystemView.jsx` | Status / tiers |
| `HelpView.jsx` | Help |
| `ExportModal.jsx` | Export flows |
| `Toast.jsx` / `Icons.jsx` | UX chrome |

### Dev vs prod UI

| Mode | Command | URL |
|------|---------|-----|
| Dev | `make ui-dev` | http://localhost:5173 |
| Prod static | `make ui-build` + `SERVE_UI_FROM_API=true` | http://localhost:8002/app |

### Frontend env

| Var | Purpose |
|-----|---------|
| `VITE_API_URL` | API base (empty = proxy/same-origin) |
| `VITE_DEV_EMAIL` / `VITE_DEV_PASSWORD` | Prefill login |
| `VITE_PORT` / `VITE_STRICT_PORT` | Dev server |
| `VITE_DEBUG_API` | Debug logging |

---

## 12. Workers and async jobs

**File:** `backend/src/worker.py`  
**Broker:** Redis (`REDIS_URL`)  
**Default time limits:** soft ~540s, hard ~600s (env override)

| Task | Trigger | Work |
|------|---------|------|
| `process_document_task` | Matter upload | Parse → chunk → embed → optional graph extract → status |
| `gap_analysis_task` | Gap workflow | Bounded agent (≤12 LLM calls) → report |
| `chat_task` | Async chat | Full RAG pipeline off-request |
| `ingest_corpus_task` | Admin corpus | Ingest uploaded law source |

**Related stub:** `backend/src/worker/erasure.py` — GDPR erasure worker stub (runbook file referenced in SECURITY.md is missing; see §25).

### Document ingest pipeline

```
Upload → security checks → store file → Celery
  → parse (PDF/DOCX/TXT/MD/EML/MSG; OCR if sparse text)
  → hierarchical / structure-aware chunking
  → optional contextual prefix for embedding text
  → bge-m3 embed → insert document_chunks
  → optional graph_extractor (T1) → graph_nodes/edges
  → ingest_status = processed | failed
```

---

## 13. Auth, RBAC, and security

### Authentication

- JWT **HS256** access tokens (`AUTH_ACCESS_EXPIRE_MINUTES`, default 15)
- Refresh tokens stored hashed (`AUTH_REFRESH_EXPIRE_DAYS`, default 7)
- Passwords: bcrypt via passlib
- **Dev master user** (`DEV_MASTER_ENABLED`) for eval/E2E — **blocked in production** by `validate_settings()`

### Dev master (local only)

| Field | Default |
|-------|---------|
| Email | `devmaster@example.com` |
| Password | `DevMasterPass123!` |

### Authorization

**Org roles (ascending):** `member` → `matter_lead` → `org_admin` → `owner`  
**Matter roles:** `viewer` → `editor` → `owner`  
**Confidentiality tiers:** `internal` / `restricted` / `privileged` — enforced in `services/access_control.py`

**Org isolation:** Cross-org access returns **404** (not 403) — existence hiding; covered in E2E.

### Security controls

| Control | Location |
|---------|----------|
| Prompt injection regex guard | `services/security.py` |
| Rate limiting | SlowAPI + Redis (`rate_limit.py`) |
| Upload security | `services/upload_security.py` |
| Production config guard | `services/config_security.py` |
| Optional Postgres RLS | `services/rls.py`, migration 010 |
| Audit hash chain | `services/audit_chain.py` |
| CORS allowlist | `ALLOWED_ORIGINS` |

### Production hardening checklist

- Strong `AUTH_SECRET_KEY` (32+ chars)
- `REGISTRATION_OPEN=false`
- `DEV_MASTER_ENABLED=false`
- `EXPOSE_OPENAPI=false`
- `LLM_PROVIDER=ollama`, clear `OPENROUTER_API_KEY`
- TLS at reverse proxy
- Restrict `ALLOWED_ORIGINS`
- `RLS_ENABLED=true`
- Run `GET /api/v1/audit/verify` after upgrades

Pen-test scope: see `SECURITY.md`. **Pen test not performed.**

---

## 14. Configuration and environment variables

**Authoritative settings object:** `backend/src/config.py` (Pydantic Settings, loads `.env`).

### Templates

| File | Use |
|------|-----|
| `.env.example` | Dev (OpenRouter T2 + Ollama T1) |
| `.env.airgap.example` | Production air-gap |

### Core runtime

| Env var | Default | Purpose |
|---------|---------|---------|
| `ENVIRONMENT` | `development` | `development` / `production` |
| `DATABASE_URL` | asyncpg URL on `:5433` | SQLAlchemy |
| `REDIS_URL` | `redis://localhost:6380/0` | Celery + cache + limits |
| `AUTH_SECRET_KEY` | `change-me-in-production` | JWT signing |
| `AUTH_ACCESS_EXPIRE_MINUTES` | `15` | Access TTL |
| `AUTH_REFRESH_EXPIRE_DAYS` | `7` | Refresh TTL |
| `REGISTRATION_OPEN` | `true` | Public register |
| `ALLOWED_ORIGINS` | localhost UI ports | CORS |
| `EXPOSE_OPENAPI` | `true` | `/docs` |
| `MAX_UPLOAD_BYTES` | 20 MB | Upload cap |
| `SERVE_UI_FROM_API` | `true` | Mount `/app` |
| `UI_DIST_PATH` | `/app/frontend/dist` | Static UI |
| `TRAINING_MOUNT_PATH` | `/training` | Fine-tune manifest |

### LLM

| Env var | Default | Purpose |
|---------|---------|---------|
| `LLM_PROVIDER` | `openrouter` | `openrouter` \| `ollama` |
| `LLM_AUX_PROVIDER` | `ollama` | T1 |
| `OLLAMA_BASE_URL` | `http://localhost:11434` | (compose uses `host.docker.internal`) |
| `OLLAMA_MODEL` | `phi3.5` (templates use Mistral) | T2 when ollama |
| `OLLAMA_AUX_MODEL` | `qwen2.5:0.5b` (templates use `3b`) | T1 |
| `OPENROUTER_API_KEY` | empty | Dev cloud key |
| `OPENROUTER_MODEL` | `microsoft/phi-4-mini-instruct` | Dev T2 |
| `OPENROUTER_BASE_URL` | OpenRouter API | |

### RAG / devices

| Env var | Default |
|---------|---------|
| `EMBEDDING_MODEL_PATH` | `/app/data/models/bge-m3` |
| `RERANKER_MODEL_PATH` | `/app/data/models/reranker` |
| `LAW_CORPUS_PATH` | `/app/data/raw/law_corpus` |
| `HYBRID_SEARCH_ENABLED` | `true` |
| `RAG_RRF_K` | `60` |
| `HYDE_ENABLED` | `false` |
| `ADAPTIVE_HYDE_ENABLED` | `true` |
| `CRAG_RETRY_ENABLED` | `true` |
| `CONTEXTUAL_RETRIEVAL_ENABLED` | `true` |
| `RAG_MIN_RERANK_SCORE` | `-2.0` |
| `CITATION_VERIFY_ENABLED` | `true` |
| `SEMANTIC_CONTEXT_MIN_COSINE` | `0.55` |
| `GRAPH_EXTRACTION_ENABLED` | `true` |
| `QUERY_CACHE_ENABLED` | `true` |
| `QUERY_CACHE_TTL_SECONDS` | `3600` |
| `AIRGAP_LATENCY_PROFILE` | auto if ollama |
| `EMBEDDING_DEVICE` / `RERANKER_DEVICE` | `auto` |

### Compliance

`RLS_ENABLED`, `AUDIT_LOG_ANSWERS`, `OCR_*`

### Branding

`BRAND_NAME`, `BRAND_TAGLINE`, `BRAND_LOGO_URL`, `BRAND_PRIMARY_COLOR`

### Observability

`TRACING_ENABLED` (stage timings in logs), `OTEL_EXPORTER_OTLP_ENDPOINT` (traces to a local collector)

### Script / CI only (not all in `config.py`)

`HF_TOKEN`, `DOWNLOAD_*`, `JURIS_API_BASE`, `CI_SKIP_LLM`, `EVAL_*`, `ADMIN_EMAIL`/`ADMIN_PASSWORD`, `COMPLIANCE_*`, `VITE_*`, `PLAYWRIGHT_API_URL`, `CELERY_TASK_*_LIMIT`, `BUNDLE_DIR`, etc.

---

## 15. Data, corpora, and storage

### On-disk layout (`data/` — gitignored)

| Path | Contents |
|------|----------|
| `data/models/bge-m3/` | Embedding weights |
| `data/models/reranker/` | Cross-encoder weights |
| `data/raw/law_corpus/` | `gdpr_en.txt`, `bgb_en.txt`, `bdsg_de.txt`, `eu_ai_act_en.txt` |
| `data/raw/cuad/` | CUAD contracts (training/eval) |
| `data/airgap-bundle/` | Offline deploy artifacts |

### Docker volumes

| Volume | Mount |
|--------|-------|
| `postgres_data` | DB files |
| `uploads_data` | `/app/src/data/uploads` |
| `hf_cache` | HuggingFace cache |
| `ollama_data` | Optional Ollama profile |

### Eval fixtures (`eval/fixtures/`)

`nda_mutual.txt`, `nda_standard.txt`, `msa_saas.txt`, `dpa_template.txt`, `employment.txt`, `license.txt`, `sow.txt`

### Golden datasets (`eval/golden/`)

| File | Cases |
|------|-------|
| `law_qa.jsonl` | 50 |
| `contract_qa.jsonl` | 20 |
| `injection.jsonl` | 15 |
| `rbac.jsonl` | 10 |
| **Total golden files** | **95** |
| Full logical suite | **~110** (includes offline/extra cases) |

### Upload formats

PDF, DOCX, TXT, MD, EML, MSG — max `MAX_UPLOAD_BYTES` (default 20 MB).

---

## 16. Setup, run, and operations

### Prerequisites

- Docker + Compose v2
- Python 3.12 (host scripts/tests)
- Node 20 (frontend)
- Optional: NVIDIA GPU + Ollama on host

### Dev quickstart

```bash
git clone https://github.com/hamdan-ishfaq/juris-slm.git
cd juris-slm
cp .env.example .env          # set AUTH_SECRET_KEY (32+ chars)
make up-gpu && make migrate   # or: make up (CPU)
# After models + law text exist:
make models                   # download bge-m3 + reranker
make download-law             # law corpus files
python scripts/run_ingest_law.py --force
make ui-dev                   # http://localhost:5173
```

**Dev login** (with `DEV_MASTER_ENABLED=true`):  
`devmaster@example.com` / `DevMasterPass123!`

### Air-gap quickstart

```bash
ollama pull mistral:7b-instruct-v0.3-q4_K_M
ollama pull qwen2.5:3b
cp .env.airgap.example .env
bash scripts/setup.sh         # IT wizard
make eval-ollama-full         # ~4h on RTX 4050
```

### Ports

| Port | Service |
|------|---------|
| 8002 | API |
| 5433 | Postgres |
| 6380 | Redis |
| 11434 | Ollama |
| 5173 | Vite UI |

### Local Python venv (scripts/tests)

```bash
python -m venv .venv
# Windows: .venv\Scripts\activate
pip install -r backend/requirements-base.txt
pip install torch --index-url https://download.pytorch.org/whl/cpu
pip install -r backend/requirements-ml.txt
```

---

## 17. Makefile targets

| Target | Action |
|--------|--------|
| `up` / `down` / `rebuild` / `logs` / `ps` | Compose lifecycle |
| `up-gpu` / `gpu-build` / `gpu-up` / `verify-gpu` | CUDA stack |
| `migrate` | `alembic upgrade head` in API container |
| `models` | Download embedding + reranker |
| `verify` | Asset verification |
| `download-law` / `ingest-law` / `ingest-law-docker` | Law corpus |
| `ui-dev` / `ui-dev-stop` / `ui-dev-restart` / `ui-build` / `ui-e2e` | Frontend |
| `test` / `test-unit` / `test-integration` | Pytest |
| `e2e` | API functional E2E |
| `eval-offline` / `eval-logical` / `eval-proxy` / `eval-native` / `eval-latency` | Eval suite |
| `eval-ollama-full` / `eval-full-local` / `eval-3x` | Combined evals |
| `airgap-bundle` / `airgap-eval` | Offline packaging / eval |
| `brutal-gate` | Fresh-stack regression |
| `regulatory-diff` | Regulatory diff tool |
| `generate-golden` | Regenerate golden JSONL |
| `fix-upload-perms` | Fix upload volume perms |

---

## 18. Scripts catalog

### Operations

| Script | Purpose |
|--------|---------|
| `setup.sh` / `setup.ps1` | Install wizard |
| `seed_admin.py` | Create admin user/org |
| `docker_up.py` | Compose helper |
| `ui_dev.sh` | Vite lifecycle |
| `compliance_evidence.sh` | Compliance zip |
| `airgap_bundle.sh` / `verify_airgap_bundle.sh` | Offline tarball |
| `verify_gpu_stack.sh` / `setup_ollama_gpu.sh` | GPU / Ollama |
| `brutal_gate.sh` | Full regression |
| `create_ollama_jurisguard.sh` | Custom Ollama model |

### Data / models

| Script | Purpose |
|--------|---------|
| `download_assets.py` | Datasets + models |
| `download_overnight.py` | Resilient downloads |
| `verify_assets.py` | Check weights on disk |
| `run_ingest_law.py` | Host-side law ingest |
| `warm_eval_fixtures.py` | Pre-ingest eval contracts |
| `generate_golden_datasets.py` | Golden JSONL |

### Eval

| Script | Purpose |
|--------|---------|
| `run_logical_eval.py` | Logical suite + pipeline metrics |
| `run_context_proxy_eval.py` | Gold-phrase proxy, not RAGAS |
| `run_native_ragas.py` | Native RAGAS + judge LLM |
| `run_latency_bench.py` | Latency |
| `run_ollama_eval_complete.sh` | Full Ollama orchestration |
| `build_ollama_eval_summary.py` | Combined summary JSON |
| `e2e_functional_test.py` | ~49-case functional E2E |
| `full_endpoint_audit.py` / `ui_endpoint_audit.py` | Coverage audits |
| `regulatory_diff.py` | Diff tool |

### Training pipeline (optional, in `experiments/finetune/`)

`01_download_datasets.py` → `02_prepare_training_data.py` → `03_generate_synthetic.py` → `04_build_final_dataset.py` → `05_smoke_test_finetune.py`  
Helpers: `training_common.py`, `finetune_common.py`, `verify_training_data.py`, `wire_cuad_samples.py`  
Reqs: `requirements-finetune.txt`, `requirements-finetune-unsloth.txt`

### Verification

`00_verify_scaffold.sh`, `00_verify_phase23.py`, `00_verify_gpu.sh`, `00_verify_datasets.sh`, `00_verify_phase2.sh`

---

## 19. Evaluation and benchmarks

> **Superseded for quality claims.** The figures below are from June 2026, on project-written tests. Measured results and known defects are in `eval/reports/baseline_2026-11/README.md`. The 2.7 min latency did not reproduce (p50 28.8 s on 2026-11-06).

### Methodology (read carefully)

- **Logical eval** checks gold **substrings** in answers/sources — regression harness, **not** formal logic.
- **15-case “RAGAS”** in reports is an **in-house proxy** — label as `context_gold_recall_proxy`.
- **Dev native-style baseline** faithfulness **0.87** in `eval/baseline.json` — cite this, not proxy 1.0.
- Re-run: `make eval-ollama-full` (~4h air-gap) or `make eval-logical` (dev).

### Headline results (June 2026, RTX 4050)

**Source:** `eval/reports/ollama_eval_summary_latest.json`  
**Models:** T2 `mistral:7b-instruct-v0.3-q4_K_M` · T1 `qwen2.5:3b`

| Metric | Dev (OpenRouter) | Air-gap (Mistral-7B) |
|--------|------------------|----------------------|
| Full logical pass | 97.3% (107/109) | **91.8% (101/110)** |
| End-to-end law hit | — | **88.6%** |
| 15-case context proxy | — | **93.3%** |
| Contract hit rate | 100% (dev gate) | **85%** |
| Refusal correctness | — | **100%** |
| Forbidden violations | 0 | **0** |
| Offline gates | 20/20 | 20/20 |
| Unit tests | 100/100 | 100/100 |
| E2E functional | 49/49 | 49/49 |
| Law chunks | — | **1,957** |

### Latency (Mistral air-gap)

| Endpoint | p50 | p90 | p95 |
|----------|-----|-----|-----|
| `/health` | 1.6 ms | 2.3 ms | 2.9 ms |
| `/corpus/stats` | 5.0 ms | 11.8 ms | 37.9 ms |
| `/chat` (full RAG) | **2.7 min** | **2.8 min** | **2.8 min** |

### Pipeline metrics (Mistral logical, `eval/reports/honest_baseline_2026-11/`)

| Metric | Value |
|--------|-------|
| `retrieval_source_hit_rate` | 86.4% |
| `answer_hit_rate` | 90.9% |
| `generation_miss` | 2 |
| `retrieval_miss_answer_hit` | 4 |

**phi3.5 baseline (Jun 19):** 79.8% logical (87/109) — same retrieval, weaker T2.

---

## 20. Testing

### Unit (offline, no LLM)

```bash
make test-unit    # ~100 tests across access, security, RRF, citation, chunking, etc.
make test         # all backend/tests/
```

Key modules under `backend/tests/`: access control, security, RBAC eval, RRF, citation verifier, law/advanced chunking, golden datasets, config security, upload security, LLM routing, gap analysis, audit chain, document parser, org isolation, phase10, playbook, query enhance/decompose, rate limits, etc.

### Integration

```bash
make test-integration   # pytest -m integration — needs live API
```

### Functional E2E

```bash
make e2e
CI_SKIP_LLM=1 make e2e   # CI mode
```

Script: `scripts/e2e_functional_test.py` (~49 cases).

### Frontend E2E

```bash
make ui-e2e   # Playwright
```

### Eval gates

```bash
make eval-offline
make eval-logical
make brutal-gate
```

---

## 21. CI/CD

Workflows in `.github/workflows/`:

| Workflow | Trigger | What runs |
|----------|---------|-----------|
| `ci.yml` | push/PR to main/master | Unit subset, E2E with `CI_SKIP_LLM`, offline logical ×3, frontend build |
| `eval.yml` | eval/backend changes + weekly Mon 03:00 UTC | Security tests, logical ×3, latency, native RAGAS, E2E |
| `functional-e2e.yml` | v2 changes | Unit + functional E2E |

CI uses Python 3.12, Node 20, Docker Compose for db/cache/api/worker.

---

## 22. Deployment modes

1. **Dev Compose:** `make up` or `make up-gpu`
2. **Prod Compose:**  
   `docker compose -f docker-compose.yml -f docker-compose.prod.yml up -d`
3. **Air-gap bundle:** `make airgap-bundle` → `data/airgap-bundle/juris-airgap-{timestamp}/`  
   (images, models, corpus, compose, `setup.sh`)
4. **Static UI from API:** `make ui-build` + `SERVE_UI_FROM_API=true` → `/app`

Compliance evidence zip:

```bash
./scripts/compliance_evidence.sh
# → dist/compliance_evidence_*.zip
```

---

## 23. Training / fine-tune (optional)

**Not part of the product.** Used for optional legal-domain GGUF experiments.

| Artifact | Path |
|----------|------|
| Colab QLoRA notebook | `experiments/finetune/phi35_legal_finetune.ipynb` |
| Ollama Modelfile | `deploy/Modelfile.example` |
| Pipeline scripts | `experiments/finetune/01_` … `05_` |
| Fine-tune deps | `experiments/finetune/requirements-finetune*.txt` |

CUAD dataset downloadable via `scripts/download_assets.py` (`cuad` target).

---

## 24. Compliance and security docs

| Document | Path | Notes |
|----------|------|-------|
| Security / pen-test scope | `SECURITY.md` | Hardening checklist |
| Control matrix | `docs/compliance/CONTROL_MATRIX.md` | SOC2/ISO/GDPR **templates** |
| Incident response | `docs/compliance/INCIDENT_RESPONSE.md` | Template |
| Architecture SVG | `docs/jurisguard_v2_architecture.svg` | Diagram |

**Not SOC 2 certified.** Compliance docs are procurement/process templates.

### Referenced but missing files

`SECURITY.md` / control matrix reference docs that are **not in the repo**:

- `docs/SSO_SETUP.md`
- `docs/GDPR_ERASURE.md`
- `docs/DISASTER_RECOVERY.md`

Erasure stub exists at `backend/src/worker/erasure.py`.

---

## 25. Known limitations and backlog

### Honest limitations

| Area | Limit |
|------|-------|
| Reasoning | Semantic + lexical + LLM soft reasoning — **no formal entailment engine** |
| Reranker | ms-marco MiniLM (web search) — not legal-fine-tuned |
| Citation verify | Label presence + cosine — not NLI |
| DLG | Small curated GDPR edges — not full graph RAG |
| RAGAS label | 15-case in-house proxy; cite faithfulness **0.87** baseline |
| Latency | Air-gap chat ~3 min p95 on 6GB GPU — research UX, not instant chat |
| Graph entities | May return empty list in some modes |
| Pen test | Not performed |
| Certification | Templates only — not SOC 2 |

### Backlog

- Legal-domain reranker fine-tune
- NLI-based citation verification
- Custom fine-tuned legal GGUF (Colab QLoRA backlog)
- Native RAGAS with judge LLM (`run_native_ragas.py` exists)
- Word tracked-changes redline export
- Pen test
- Missing runbooks: GDPR erasure, DR

---

## 26. Development history (phases)

High-level evolution (from commit history + docs):

| Phase | Theme |
|-------|-------|
| 0 | Stabilization, E2E gate |
| 1 | RBAC, LLM provider swap |
| 2 | Hybrid retrieval engine |
| 3 | Eval harness, security hardening, RAG fool-proofing |
| 4–10 | Enterprise platform: matters, Graph RAG, React UI, SSO/SCIM, legal hold, WORM, clause library, deadlines (all later removed), handoff |
| Cleanup | Legacy V1 removed; repo is v2-only |

App version string: **0.5.0**.

---

## 27. File map (critical paths)

| Path | Role |
|------|------|
| `backend/src/main.py` | FastAPI app, middleware, router mount, UI mount |
| `backend/src/config.py` | All settings |
| `backend/src/db.py` | ORM models |
| `backend/src/deps.py` | Auth dependencies |
| `backend/src/worker.py` | Celery tasks |
| `backend/src/ingest_law.py` | Law corpus ingest CLI |
| `backend/src/routers/*` | HTTP surface |
| `backend/src/services/rag.py` | RAG brain |
| `backend/src/services/vector_store.py` | Hybrid search SQL |
| `backend/src/services/llm_client.py` | T2 generation + system prompt |
| `frontend/src/App.jsx` | SPA shell |
| `frontend/src/lib/api.js` | API client |
| `scripts/setup.sh` | Air-gap install |
| `scripts/run_ollama_eval_complete.sh` | Full eval |
| `eval/golden/*.jsonl` | Golden cases |
| `eval/reports/ollama_eval_summary_latest.json` | Benchmark truth |
| `.env.example` / `.env.airgap.example` | Config templates |
| `Makefile` | Ops interface |
| `docker-compose*.yml` | Deploy |

---

## 28. Conventions

### Naming

- Routers: `routers/{feature}.py`, prefix `/api/v1/...`
- Services: one concern per module under `services/`
- Migrations: `{NNN}_{description}.py`
- Tests: `test_{feature}.py`; integration via marker
- Scripts: `01_`–`05_` training; `run_*` eval; `verify_*` checks; `00_verify_*` phase gates
- Env: `SCREAMING_SNAKE_CASE` via pydantic `validation_alias`

### Git

- Ignore: `data/`, `.env`, `*.gguf`, checkpoints, uploads
- Keep: `eval/reports/*_latest.json`
- Do not commit secrets

### API behavior

- Cross-org → **404**
- Chat rate-limited
- Gap analysis heavily rate-limited
- Production rejects weak secrets / open registration / dev master

---

## 29. Day-one checklist for a new engineer

1. Clone repo
2. Read this document + skim `README.md` and `SECURITY.md`
3. Copy `.env.example` → `.env`; set `AUTH_SECRET_KEY`
4. `make up-gpu` (or `make up`) + `make migrate`
5. `make models` + `make download-law` + ingest law
6. `make ui-dev`; login as dev master
7. Hit OpenAPI at `/docs`; try one research chat
8. Run `make test-unit` and `CI_SKIP_LLM=1 make e2e`
9. Read `services/rag.py` end-to-end once
10. Skim latest eval summary JSON before changing retrieval or prompts

---


## Appendix A — Related docs (specialty only)

| Doc | Use instead of this handoff when… |
|-----|-----------------------------------|
| `README.md` | You need a short public overview |
| `SECURITY.md` | Pen-test scoping / hardening |
| `docs/compliance/*` | Procurement control narratives |
| OpenAPI `/docs` | Live request/response schemas |

**This file is the single complete project handoff.** Prefer updating this document when the system of record changes.

---

*JurisGuard V2 · Complete Project Handoff · June 2026 · App v0.5.0*

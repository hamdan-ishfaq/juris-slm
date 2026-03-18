# Technical Audit Report

**Project:** JurisGuard / BEWEIS (Secure Legal RAG Platform)  
**Date:** 2026-03-16  
**Repository Root:** `juris_full_project`  
**Audit Type:** Source/config/test implementation audit + architecture/risk review

## 1. Executive Summary

This repository is an advanced MVP/prototype of a secure legal RAG stack with real implementation across backend, frontend, and containerized infrastructure.

The project has substantial working functionality:
- JWT authentication and role-based controls
- PDF upload and ingestion pipeline
- Hybrid retrieval (FAISS + BM25 + cross-encoder reranking)
- LLM query generation with prompt hardening and output sanitization
- Chat history persistence and Redis response caching
- Owner-only user management endpoints
- Backend and frontend test suites with basic e2e smoke testing

However, it is **not fully production-hardened yet** due to dependency manifest drift, configuration mismatches, missing migration/CI pipelines, exposed debug surfaces, and a few implementation inconsistencies.

### Overall Maturity
- **Product functionality:** High
- **Operational hardening:** Medium
- **Security hardening:** Medium
- **Release readiness:** Medium (not low, not fully production-grade)

## 2. Audit Scope And Coverage

### 2.1 Files Reviewed
Primary code/config/test surfaces reviewed:
- `backend/src/**/*.py`
- `backend/config/*.py`, `backend/config/config.yaml`
- `backend/tests/**/*.py`
- `frontend/src/**/*.{js,jsx,css}`
- `frontend/e2e/*`
- `frontend/package.json`, `frontend/package-lock.json`
- `docker-compose.yml`
- `backend/Dockerfile`
- `backend/requirements.txt`
- `README.md`

### 2.2 Authored Scope Metrics
Counted with exclusions for generated/vendor paths (`node_modules`, `dist`, `.git`, `.venv`, caches):
- **Authored scoped files:** `61`
- **Authored scoped lines:** `6812`

## 3. System Architecture Breakdown

## 3.1 Runtime Topology
- **Backend API:** FastAPI app factory in `backend/src/api.py`, entrypoint `backend/src/main.py`
- **Frontend SPA:** React + Vite in `frontend/src`
- **Database:** PostgreSQL via SQLAlchemy async engine in `backend/src/db.py`
- **Cache:** Redis async client in `backend/src/query.py`
- **Vector Store:** FAISS persisted locally in `backend/src/ingestion.py`
- **LLM + Embeddings + Reranker:** loaded through `backend/src/models.py`

## 3.2 Startup Lifecycle (Backend)
Defined in `backend/src/api.py` lifespan:
1. Initialize DB (`init_db`)
2. Set auth config (`set_auth_config`)
3. Construct managers (`ModelManager`, `SecurityManager`, `IngestionManager`, `QueryManager`)
4. Inject managers into routers
5. Background thread preloads embedding model and LLM
6. On shutdown: unload models and close DB

## 3.3 API Surface
Main routers:
- `/auth/*` -> registration/login/profile (`backend/src/routers/auth.py`)
- `/chat/*` -> query/history/clear/trace (`backend/src/routers/chat.py`)
- `/documents/*` -> upload/metadata/semantic search (`backend/src/routers/documents.py`)
- `/admin/*` -> owner user management (`backend/src/routers/admin.py`)

Additional app routes:
- `/health`
- `/evaluate`
- `/debug/*` diagnostics in `backend/src/api.py`
- Static SPA serving fallback from frontend dist

## 4. Feature Inventory And Implementation Status

## 4.1 Authentication + Authorization
**Status:** Implemented, generally solid.

Implemented:
- Password hashing and verification via bcrypt/passlib (`backend/src/auth.py`)
- JWT creation/verification and expiry handling (`backend/src/auth.py`)
- Register/login/me endpoints (`backend/src/routers/auth.py`)
- Role claims in JWT (`role` in token payload)
- Owner-only guard for admin endpoints (`require_owner` in `backend/src/routers/admin.py`)

Gaps:
- Frontend localStorage key mismatch causes auth-state inconsistencies (details in findings)

**Completeness estimate:** 85%

## 4.2 RBAC And Access Control
**Status:** Implemented at app/domain levels.

Implemented:
- Roles in DB enum: `user`, `admin`, `owner` (`backend/src/db.py`)
- Document access level enum: `level_1`, `level_2`, `level_3` (`backend/src/db.py`)
- Query filtering by role in `QueryManager.query()` (`backend/src/query.py`)
- Owner-only role mutation/deletion in admin router

Gaps:
- Access model has partial overlap of role tags (`role`) and document access levels (`access_level`) with limited policy unification

**Completeness estimate:** 80%

## 4.3 Document Ingestion Pipeline
**Status:** Substantial implementation.

Implemented:
- PDF-only upload endpoint with extension/MIME/size checks (`backend/src/routers/documents.py`)
- Temp-file handling and cleanup
- PDF extraction via `pdfplumber` (`backend/src/ingestion.py`)
- Hierarchical chunking: parent (~1000 chars) and child (~200 chars)
- Parent chunks persisted in SQL (`ParentChunk` table)
- Child chunk embeddings indexed in FAISS with metadata persistence (`faiss.index`, `metadata.pkl`)

Gaps:
- Evaluation module calls non-existent ingestion method (`ingest`) instead of `ingest_pdf`
- No dedup/versioning strategy for repeated uploads

**Completeness estimate:** 80%

## 4.4 Retrieval + Generation (RAG)
**Status:** Strong implementation for MVP.

Implemented in `backend/src/query.py`:
- FAISS vector retrieval
- BM25 lexical retrieval (`rank_bm25`)
- Reciprocal rank fusion + weighted normalization
- Cross-encoder reranking
- Role-based filtering of candidate chunks
- Prompt construction with strict delimiters and system instructions
- LLM generation with configurable sampling params
- Output sanitization for instruction leakage markers

**Completeness estimate:** 82%

## 4.5 Prompt Security Layers
**Status:** Present and thoughtful.

Implemented:
- Hard regex pattern filter (`HardFilter` in `backend/src/security.py`)
- Sentinel classifier (zero-shot if available, heuristic fallback)
- Chunk sensitivity tagging and role assignment
- Prompt-injection-resistant prompt framing
- Post-generation sanitization to strip leaked scaffolding

Gaps:
- Limited automated adversarial testing for jailbreak/injection regressions

**Completeness estimate:** 78%

## 4.6 Conversational Memory + Audit
**Status:** Implemented.

Implemented:
- Chat message persistence (`ChatMessage` model)
- History endpoint + clear endpoint
- Sliding context window (last 6 messages)
- QueryTrace audit model and async write path

**Completeness estimate:** 85%

## 4.7 Caching
**Status:** Implemented.

Implemented:
- Redis lazy connect
- Deterministic cache key from query+role
- TTL storage for answer + trace payload

Gap:
- Redis host probing does not properly leverage configured `REDIS_URL`

**Completeness estimate:** 75%

## 4.8 Evaluation Framework
**Status:** Partially implemented.

Implemented:
- 10-case test matrix in `backend/src/eval.py`
- `/evaluate` endpoint with result aggregation and status counts

Gap:
- Ingestion call mismatch can break evaluation bootstrap path

**Completeness estimate:** 55%

## 4.9 Frontend Product Flows
**Status:** Most core routes implemented.

Implemented:
- Route protection wrappers in `frontend/src/App.jsx`
- Login/register page
- Chat page with history load + clear
- Upload page with multi-file UX and status
- Diagnostics/evaluation trigger page
- Owner-only user management page
- API interceptors for auth and errors

Gaps:
- Mixed visual systems and style conventions (not unified)
- Legacy/unused pages suggest refactor debt (`Dashboard`, `Landing`, `Contact`, `Evaluation` variant)
- Auth-state key mismatch with Navbar

**Completeness estimate:** 70%

## 4.10 Testing
**Status:** Good start, not exhaustive.

Implemented:
- Backend async tests for auth/chat/documents/api
- Frontend unit tests for login/chat basics
- Playwright smoke e2e path

Missing:
- Full ingestion integration tests with real FAISS persistence
- Cache behavior tests
- Security adversarial tests
- CI execution pipeline

**Completeness estimate:** 65%

## 5. Technology And Library Versions

## 5.1 Backend Dependencies (Declared)
From `backend/requirements.txt`:
- `passlib[bcrypt]==1.7.4`
- `bcrypt==4.1.3`
- `python-jose[cryptography]==3.3.0`
- `sqlalchemy[asyncio]==2.0.23`
- `asyncpg==0.29.0`
- `psycopg2-binary==2.9.9`
- `redis==5.0.1`
- `slowapi==0.1.9`
- `rank-bm25` (unpinned)
- `pytest==8.4.2`
- `pytest-asyncio==1.1.0`
- `httpx==0.28.1`
- `aiosqlite==0.21.0`

Container-pinned (in `backend/Dockerfile`):
- `torch==2.1.2+cu121`
- `torchaudio==2.1.2+cu121`
- `torchvision==0.16.2+cu121`

## 5.2 Frontend Dependencies
From `frontend/package.json`:
- `react ^19.2.0`
- `react-dom ^19.2.0`
- `react-router-dom ^7.12.0`
- `axios ^1.13.2`
- `framer-motion ^12.24.11`
- `jwt-decode ^4.0.0`
- `lucide-react ^0.562.0`
- `react-hot-toast ^2.6.0`
- `vite ^5.4.0`
- `tailwindcss ^3.4.17`
- `vitest ^2.1.9`
- `@playwright/test ^1.55.0`

## 5.3 Infra Images
From `docker-compose.yml` and `backend/Dockerfile`:
- `postgres:15-alpine`
- `redis:7-alpine`
- `nvidia/cuda:12.1.1-runtime-ubuntu22.04`

## 6. Findings (Severity Ranked)

## 6.1 High Severity

### H1. Backend requirements are incomplete for actual imports
Evidence:
- Runtime imports in `backend/src/*.py` include modules not present in `backend/requirements.txt` (e.g., FastAPI, uvicorn, pydantic/yaml stack, transformers/sentence-transformers/peft, scikit-learn, faiss, pdfplumber, python-multipart)

Impact:
- Fresh environment setup likely fails.
- Production reproducibility weak.

Recommendation:
- Rebuild `backend/requirements.txt` from import graph and pin exact versions (or generate lockfile).

### H2. Evaluation ingestion call mismatch
Evidence:
- `backend/src/eval.py` calls `ingestion_manager.ingest(...)`
- Ingestion manager defines `ingest_pdf(...)` in `backend/src/ingestion.py`

Impact:
- `/evaluate` can fail if ingestion is needed.

Recommendation:
- Replace invalid call and add regression test.

### H3. Frontend auth state inconsistency due to key mismatch
Evidence:
- API client stores: `access_token`, `user_email`, `user_role` in `frontend/src/lib/api.js`
- Navbar reads: `token`, `username`, `role` in `frontend/src/components/Navbar.jsx`

Impact:
- Inconsistent authenticated UI and role visibility.

Recommendation:
- Standardize storage keys app-wide.

## 6.2 Medium Severity

### M1. CORS wildcard + credentials mix is unsafe/invalid
Evidence:
- `api.origins: ["*"]` in `backend/config/config.yaml`
- `allow_credentials=True` in `backend/src/api.py`

Impact:
- Browser credential behavior can be invalid and security posture weak.

Recommendation:
- Use explicit trusted origins only; separate dev/prod origin sets.

### M2. Exposed unauthenticated debug endpoints
Evidence:
- Public `/debug/metadata`, `/debug/semantic`, `/debug/trace`, `/debug/last` in `backend/src/api.py`

Impact:
- Potential information disclosure.

Recommendation:
- Protect behind owner/admin auth or disable in production profile.

### M3. Config/secret source ambiguity
Evidence:
- `AuthConfig` validator in `backend/config/settings.py` enforces `AUTH_SECRET_KEY` env var
- `backend/config/config.yaml` still defines `auth.secret_key`

Impact:
- Operational confusion and startup surprises.

Recommendation:
- Single source-of-truth policy for secrets.

### M4. Redis URL not directly consumed
Evidence:
- `backend/src/query.py` performs host probing rather than parsing `REDIS_URL`

Impact:
- Environment settings may be ignored unexpectedly.

Recommendation:
- Parse and use `REDIS_URL` first, host probing only as fallback.

### M5. Dev proxy mismatch
Evidence:
- `frontend/vite.config.js` proxies only `/api`
- frontend client uses `/auth`, `/chat`, `/documents`, `/admin`, `/evaluate`

Impact:
- Local dev behavior inconsistent unless same-origin backend used.

Recommendation:
- Add proxy rules for actual API path prefixes.

## 6.3 Low Severity

### L1. Documentation drift
Evidence:
- `README.md` references Phi-3 path while `backend/config/config.yaml` currently sets TinyLlama.

Impact:
- Onboarding confusion.

Recommendation:
- Align docs with active config and supported model profiles.

### L2. Style/theme inconsistency across pages
Evidence:
- Mixed neutral vs dark/purple styling patterns across page modules.

Impact:
- UX inconsistency and maintenance friction.

Recommendation:
- Consolidate page styles under shared design system tokens.

## 7. Missing Components / Technical Debt

- No migration system (no Alembic folder/migration history found)
- No CI pipeline (`.github/workflows` absent)
- No explicit environment matrix/testing matrix docs for GPU/CPU fallback
- No production profile that disables debug-only surfaces
- No formal dependency lock for backend comparable to frontend lockfile

## 8. Security Posture Snapshot

Implemented controls:
- JWT + expiry
- bcrypt password hashing
- upload validation checks
- rate limiting on auth/upload
- prompt hardening and output cleanup
- role-aware retrieval filtering

Hardening needed:
- tighten CORS
- restrict debug routes
- unify secret loading strategy
- remove/default-rotate sample secrets in tracked files

## 9. Testing Posture Snapshot

Strengths:
- backend async tests cover auth/chat/upload basics
- frontend unit tests cover key UX paths
- e2e smoke validates critical happy-path

Gaps:
- no deep retrieval quality regression suite
- no prompt-injection stress tests
- no CI enforcement

## 10. Production Readiness Assessment

Current readiness: **Advanced MVP / pre-production hardening phase**

Notable strengths:
- Non-trivial, real backend implementation with integrated RAG pipeline
- Working user and document workflows
- Clear modular architecture

Blocking items before “production-ready” label:
1. Dependency manifest correctness
2. Evaluation path bug fix
3. Auth-state consistency in frontend
4. CORS/debug route hardening
5. Migration + CI pipeline introduction

## 11. Prioritized Remediation Roadmap

### Phase 1 (Immediate, 1-3 days)
1. Fix `eval.py` ingestion call mismatch
2. Unify frontend localStorage auth keys
3. Lock down debug endpoints and CORS policy
4. Regenerate and pin backend dependencies

### Phase 2 (Short-term, 3-7 days)
1. Add Alembic migrations
2. Add CI for lint + tests
3. Add Redis URL first-class config support
4. Align README and deployment docs with current model/runtime

### Phase 3 (Stabilization, 1-2 weeks)
1. Expand integration/e2e and security adversarial tests
2. Introduce environment profiles (dev/staging/prod)
3. Add observability/metrics/tracing baselines

## 12. Implementation Completeness Scorecard

- Authentication: **85%**
- RBAC: **80%**
- Ingestion: **80%**
- Retrieval/Generation: **82%**
- Security Layering: **78%**
- Chat Memory/Audit: **85%**
- Caching: **75%**
- Evaluation Suite: **55%**
- Frontend Product UX: **70%**
- Test Coverage: **65%**
- DevOps Hardening: **58%**

**Weighted overall implementation maturity:** **~74%**

---

## Appendix A: Key Referenced Files

- `backend/src/api.py`
- `backend/src/query.py`
- `backend/src/ingestion.py`
- `backend/src/models.py`
- `backend/src/security.py`
- `backend/src/auth.py`
- `backend/src/db.py`
- `backend/src/eval.py`
- `backend/src/routers/auth.py`
- `backend/src/routers/chat.py`
- `backend/src/routers/documents.py`
- `backend/src/routers/admin.py`
- `backend/config/settings.py`
- `backend/config/config.yaml`
- `backend/requirements.txt`
- `backend/Dockerfile`
- `frontend/src/App.jsx`
- `frontend/src/lib/api.js`
- `frontend/src/components/Navbar.jsx`
- `frontend/src/pages/Login.jsx`
- `frontend/src/pages/Chat.jsx`
- `frontend/src/pages/Upload.jsx`
- `frontend/src/pages/Diagnostics.jsx`
- `frontend/src/pages/ManageUsers.jsx`
- `frontend/package.json`
- `frontend/vite.config.js`
- `docker-compose.yml`
- `README.md`

# JurisGuard MASTER STRATEGY — Parts 13–18

> **Merged into:** [JurisGuard_MASTER_STRATEGY.md](./JurisGuard_MASTER_STRATEGY.md)  
> Regenerate master via `python scripts/build_master_strategy_doc.py`. Keep this file as source for appendices detail.

**Document:** JurisGuard MASTER STRATEGY (Appendix)  
**Version:** 1.0  
**Date:** June 2026  
**Scope:** Parts 13–18 — feature checklist, timeline, API appendix, risks, glossary, references  
**Companion docs:** [PHASE_IMPLEMENTATION_PLAN.md](./PHASE_IMPLEMENTATION_PLAN.md), [PROJECT_AUDIT_AND_REBRAND.md](./PROJECT_AUDIT_AND_REBRAND.md)

---

## Part 13 — Master Feature Checklist

Every deliverable from the phase plan, organized by workstream. **Status legend:**

| Status | Meaning |
|--------|---------|
| **Done** | Implemented and verified (E2E or manual) |
| **Partial** | Code exists but incomplete, unreliable, or not production-ready |
| **Planned** | Specified in phase plan; not started |
| **Cancelled** | Explicitly deprecated per strategy decision |
| **Deferred** | Valid work; pushed beyond current 34-week horizon |

### 13.1 Phase 0 — Stabilization & Repo Hygiene (Week 1)

| ID | Feature | Category | Phase | Status | Notes |
|----|---------|----------|-------|--------|-------|
| 0.1.1 | Celery worker in Docker Compose | ops | 0 | Done | `docker-compose.yml` — worker service added |
| 0.1.2 | Shared uploads volume (API + worker) | ops | 0 | Done | Worker can read uploaded files |
| 0.1.3 | Shared HF cache volume | ops | 0 | Done | Prevents re-download per container |
| 0.1.4 | Ollama `host.docker.internal` routing | ops | 0 | Done | LLM reachable from containers |
| 0.1.5 | Alembic mount in compose | ops | 0 | Done | Migrations match host revisions |
| 0.1.6 | CPU torch in Dockerfile (not CUDA) | ops | 0 | Done | Smaller image; embed/rerank on CPU |
| 0.1.7 | Celery solo pool | ops | 0 | Done | Prevents ML fork OOM on 4050 |
| 0.1.8 | Injection guard returns HTTP 400 | security | 0 | Done | `chat.py`, `rag.py` |
| 0.1.9 | Compare endpoint dual RAG (doc + law) | RAG | 0 | Done | `matters.py` — merges both answers |
| 0.1.10 | Graph JSON parsing robustness | graph | 0 | Partial | `graph_extractor.py` — still unreliable |
| 0.1.11 | Worker asyncio.run fix (Python 3.12) | bugs | 0 | Done | Celery tasks complete |
| 0.1.12 | Non-blocking ML preload on API startup | ops | 0 | Done | Health responds while models warm |
| 0.1.13 | Skip empty local model dirs | bugs | 0 | Done | Faster HF fallback |
| 0.1.14 | Functional E2E test script (27/27) | eval | 0 | Done | `scripts/e2e_functional_test.py` |
| 0.1.15 | matters.py router regression fix | bugs | 0 | Done | All matter routes registered |
| 0.2.1 | bge-m3 + reranker weights on disk | bugs | 0 | Partial | Run `download_assets.py`; may still HF-fallback |
| 0.2.2 | Alembic upgrade documented in runbook | ops | 0 | Planned | `docs/RUNBOOK.md` not yet extracted |
| 0.2.3 | Orphan Ollama container cleanup docs | ops | 0 | Planned | Single Ollama instance policy |
| 0.2.4 | Deprecate `test_e2e_comprehensive.py` | eval | 0 | Planned | Wrong port 8000; misleading thresholds |
| 0.2.5 | Worker non-root user | security | 0 | Planned | Dockerfile `USER` directive |
| 0.2.6 | Compare parallel LLM calls | RAG | 0 | Planned | `asyncio.gather` with semaphore(1) |
| 0.2.7 | Celery worker health in `/api/v1/status` | ops | 0 | Planned | Celery inspect ping |
| 0.3.1 | `legacy/v1/` restructure plan | rebrand | 0 | Planned | Archive root `backend/`, `frontend/` |
| 0.3.2 | Pin Python deps with hashes | ops | 0 | Planned | Reproducible builds |
| 0.3.3 | One-command dev (`Makefile` / `dev_up.sh`) | ops | 0 | Planned | Onboarding friction |
| 0.4.1 | `verify_assets.py` passes | ops | 0 | Planned | Model integrity check |
| 0.4.2 | E2E 27/27 in CI | eval | 0 | Planned | GitHub Actions workflow |
| 0.4.3 | `docs/RUNBOOK.md` | ops | 0 | Planned | Extract from README |

### 13.2 Phase 1 — Security, RBAC & Compliance (Weeks 2–4)

| ID | Feature | Category | Phase | Status | Notes |
|----|---------|----------|-------|--------|-------|
| 1.1.1 | `users.role` column migration | security | 1 | Planned | Alembic 004 — `member\|matter_lead\|org_admin\|owner` |
| 1.1.2 | `organizations` table | security | 1 | Planned | Multi-tenant foundation |
| 1.1.3 | `users.org_id` FK | security | 1 | Planned | Org scoping |
| 1.1.4 | `matter_members` table | security | 1 | Planned | Collaborator roles |
| 1.1.5 | `matter_documents.confidentiality` | security | 1 | Planned | `internal\|restricted\|privileged` |
| 1.2.1 | JWT claims: `role`, `org_id`, `sub` | security | 1 | Planned | `auth_utils.py` extension |
| 1.2.2 | `require_matter_access()` dependency | security | 1 | Planned | `deps.py` — min_role enforcement |
| 1.2.3 | Document confidentiality vs role | security | 1 | Planned | Port V1 `_is_accessible` logic |
| 1.2.4 | Retrieval-layer RBAC filter | security | 1 | Planned | `search_similar()` accessible doc IDs |
| 1.2.5 | Law corpus access policy per org | security | 1 | Planned | Config flag |
| 1.3.1 | Register with optional `org_name` | security | 1 | Planned | First user creates org |
| 1.3.2 | `/auth/me` returns role + org_id | security | 1 | Planned | Extend `UserResponse` |
| 1.3.3 | `POST /matters/{id}/members` | security | 1 | Planned | Invite collaborator |
| 1.3.4 | `DELETE /matters/{id}/members/{user_id}` | security | 1 | Planned | Remove collaborator |
| 1.4.1 | `GET /api/v1/admin/users` | security | 1 | Planned | `org_admin`, `owner` only |
| 1.4.2 | `PUT /api/v1/admin/users/{id}/role` | security | 1 | Planned | `owner` only |
| 1.4.3 | `DELETE /api/v1/admin/users/{id}` | security | 1 | Planned | `owner` only |
| 1.4.4 | Admin router (`routers/admin.py`) | security | 1 | Planned | Register in `main.py` |
| 1.5.1 | Rate limit: login 5/min/IP | security | 1 | Planned | Port V1 `slowapi` |
| 1.5.2 | Rate limit: register 3/min/IP | security | 1 | Planned | Redis backend |
| 1.5.3 | Rate limit: chat 10/min/user | security | 1 | Planned | Per-user key |
| 1.5.4 | Rate limit: upload 5/hour/user | security | 1 | Planned | Abuse prevention |
| 1.6.1 | L1 keyword injection heuristics | security | 0 | Done | `rag.py` suspicious phrase list |
| 1.6.2 | L2 regex hard filter | security | 1 | Planned | Port V1 `security.py` |
| 1.6.3 | L3 BART Sentinel classifier (CPU) | security | 1b | Deferred | ~1.5 GB RAM; lazy load |
| 1.6.4 | L4 output sanitizer | security | 1 | Planned | Strip system prompt leaks |
| 1.7.1 | `GET /api/v1/audit` paginated | security | 1 | Planned | `org_admin`+ |
| 1.7.2 | `GET /api/v1/audit/export` CSV | security | 1 | Planned | DPO compliance export |
| 1.8.1 | Alembic 004 applied | security | 1 | Planned | Migration in CI |
| 1.8.2 | Unit test: cross-user chunk isolation | security | 1 | Planned | Retrieval layer |
| 1.8.3 | E2E: cross-matter blocked at retrieval | security | 1 | Planned | Not just 404 on analyze |
| 1.8.4 | Rate limit integration tests | security | 1 | Planned | 429 responses |

### 13.3 Phase 2 — Retrieval Engine Upgrade (Weeks 5–8)

| ID | Feature | Category | Phase | Status | Notes |
|----|---------|----------|-------|--------|-------|
| 2.1.1 | `content_tsv tsvector` column | RAG | 2 | Planned | Alembic 005 |
| 2.1.2 | GIN index on `content_tsv` | RAG | 2 | Planned | Full-text search |
| 2.1.3 | `hybrid_search()` SQL function | RAG | 2 | Planned | Vector + FTS + RRF |
| 2.1.4 | Replace `search_similar()` in `rag.py` | RAG | 2 | Planned | Hybrid as default |
| 2.1.5 | German FTS config (`pg_catalog.german`) | RAG | 2 | Planned | BGB/GDPR tokenization |
| 2.1.6 | Backfill tsvector for 1,862+ chunks | RAG | 2 | Planned | Migration script |
| 2.2.1 | Wire `services/hyde.py` | RAG | 2 | Planned | File exists; not connected |
| 2.2.2 | `settings.hyde_enabled` config flag | RAG | 2 | Planned | Default `False` |
| 2.2.3 | `use_hyde` on `ChatRequest` | RAG | 2 | Planned | Per-request toggle |
| 2.2.4 | HyDE Ollama call serialization | RAG | 2 | Planned | Queue with chat |
| 2.3.1 | Wire `advanced_chunking.py` into ingest | RAG | 2 | Planned | Article/section boundaries |
| 2.3.2 | Law chunk metadata enrichment | RAG | 2 | Planned | `article`, `paragraph`, `title` |
| 2.3.3 | Force re-ingest law corpus | RAG | 2 | Planned | `ingest_law.py --force` |
| 2.4.1 | Contextual retrieval prepends | RAG | 2 | Planned | Anthropic pattern at embed time |
| 2.4.2 | Re-embed law corpus post-contextual | RAG | 2 | Planned | Updated embeddings |
| 2.5.1 | Confidence gate (`rag_min_rerank_score`) | RAG | 2 | Planned | Refusal on low rerank |
| 2.5.2 | "Insufficient context" response | RAG | 2 | Planned | No hallucination path |
| 2.6.1 | `services/citation_verifier.py` | RAG | 2 | Planned | Post-generation check |
| 2.6.2 | Citation pattern parser (`Art. \d+`) | RAG | 2 | Planned | GDPR/BGB patterns |
| 2.6.3 | Mismatch disclaimer or regenerate | RAG | 2 | Planned | One retry max |
| 2.7.1 | **Clause-first parent-child chunking** (contracts + law) | RAG | 2 | Planned | Whole clauses via `clause_chunker.py`; child embed, `parent_content` in metadata — replaces 1200-char splits |
| 2.7.1b | **Full chunk text in API `sources[]`** | RAG | 2 | Planned | `rag.py` must return `content`, `chunk_id`, `parent_content` for UI |
| 2.7.2 | UI shows exact retrieved chunks | frontend | 4 | Planned | `RetrievedSourcesPanel` — no truncation; parent expand |
| 2.7.2 | `parent_chunk_id` in metadata JSONB | RAG | 2 | Planned | No new table initially |
| 2.8.1 | Query decomposition for compare | RAG | 2 | Planned | Sub-queries + RRF merge |
| 2.8.2 | Rule-based decompose (or 1 LLM call) | RAG | 2 | Planned | Compare endpoint only |
| 2.9.1 | Hybrid A/B vs vector-only on eval | eval | 2 | Planned | Phase 3 golden set |
| 2.9.2 | Citation verifier unit tests | eval | 2 | Planned | `tests/test_citation_verifier.py` |
| 2.9.3 | p95 warm chat < 30 s (HyDE off) | eval | 2 | Planned | Benchmark harness |

### 13.4 Phase 3 — Evaluation Harness & CI Gates (Weeks 9–10)

| ID | Feature | Category | Phase | Status | Notes |
|----|---------|----------|-------|--------|-------|
| 3.1.1 | `eval/golden/law_qa.jsonl` (50 items) | eval | 3 | Planned | GDPR/BGB with gold articles |
| 3.1.2 | `eval/golden/contract_qa.jsonl` (20 items) | eval | 3 | Planned | Matter-document Q&A |
| 3.1.3 | `eval/golden/injection.jsonl` (15 items) | eval | 3 | Planned | Adversarial → expect 400 |
| 3.1.4 | `eval/golden/rbac.jsonl` (10 items) | eval | 3 | Planned | Cross-tenant deny |
| 3.2.1 | `scripts/requirements-eval.txt` | eval | 3 | Planned | `ragas`, `datasets` |
| 3.2.2 | `scripts/run_ragas_eval.py` | eval | 3 | Planned | Local API runner |
| 3.2.3 | RAGAS: `context_precision` | eval | 3 | Planned | Retrieved relevance |
| 3.2.4 | RAGAS: `context_recall` | eval | 3 | Planned | Gold info retrieved |
| 3.2.5 | RAGAS: `faithfulness` | eval | 3 | Planned | Answer grounded |
| 3.2.6 | RAGAS: `answer_relevancy` | eval | 3 | Planned | On-topic |
| 3.2.7 | CI fail if faithfulness drops > 5% | eval | 3 | Planned | PR gate on RAG changes |
| 3.3.1 | `scripts/run_logical_eval.py` | eval | 3 | Planned | Custom non-RAGAS checks |
| 3.3.2 | Citation existence check | eval | 3 | Planned | `Art. N` ∈ sources |
| 3.3.3 | Gold article hit check | eval | 3 | Planned | Substring in source union |
| 3.3.4 | Refusal correctness check | eval | 3 | Planned | Low-confidence → no hallucination |
| 3.3.5 | RBAC leak check | eval | 3 | Planned | User A ≠ User B chunks |
| 3.4.1 | Chat p95 warm < 25 s | eval | 3 | Planned | Laptop SLO |
| 3.4.2 | Chat p95 cold < 90 s | eval | 3 | Planned | First-call SLO |
| 3.4.3 | Analyze p95 warm < 30 s | eval | 3 | Planned | Matter-scoped |
| 3.4.4 | Ingest 5-page TXT < 45 s | eval | 3 | Planned | Celery worker |
| 3.4.5 | Hybrid search only < 200 ms | eval | 3 | Planned | No LLM |
| 3.4.6 | k6 or locust light (5 users max) | eval | 3 | Planned | Concurrency cap |
| 3.5.1 | Golden set committed (no client data) | eval | 3 | Planned | Synthetic only |
| 3.5.2 | `eval/baseline.json` checked in | eval | 3 | Planned | RAGAS baseline |
| 3.5.3 | GitHub Action `eval.yml` | eval | 3 | Planned | Optional nightly |

### 13.5 Phase 4 — Frontend (Weeks 11–14)

| ID | Feature | Category | Phase | Status | Notes |
|----|---------|----------|-------|--------|-------|
| 4.1.1 | React 19 + Vite + TypeScript + Tailwind | frontend | 4 | Planned | Match V1 stack |
| 4.1.2 | Axios client → `:8002/api/v1` | frontend | 4 | Planned | API base URL |
| 4.1.3 | JWT storage (httpOnly cookie preferred) | frontend | 4 | Planned | Else localStorage |
| 4.2.1 | `/login` — register + login | frontend | 4 | Planned | Auth flow |
| 4.2.2 | `/chat` — RAG chat + source panel | frontend | 4 | Planned | `use_law_corpus` toggle |
| 4.2.3 | `/matters` — list/create | frontend | 4 | Planned | Matter workspace |
| 4.2.4 | `/matters/:id` — upload, status, analyze, compare | frontend | 4 | Planned | Core matter UX |
| 4.2.5 | `/matters/:id/documents/:docId` — graph view | frontend | 4 | Planned | Replaced by DLG in Phase 5 |
| 4.2.6 | `/admin/users` — role management | frontend | 4 | Planned | `org_admin`+ |
| 4.2.7 | `/audit` — log table + export | frontend | 4 | Planned | Compliance UI |
| 4.2.8 | `/settings` — model status | frontend | 4 | Planned | `/api/v1/status` |
| 4.3.1 | Source panel with article labels + scores | frontend | 4 | Planned | Trust UX |
| 4.3.2 | "Insufficient context" UI state | frontend | 4 | Planned | API refusal display |
| 4.3.3 | Confidentiality selector on upload | frontend | 4 | Planned | Phase 1 dependency |
| 4.3.4 | No unverified performance claims in UI | frontend | 4 | Planned | Phase 3 baseline required |
| 4.4.1 | Playwright smoke: login → chat → upload → analyze | eval | 4 | Planned | CI smoke |
| 4.4.2 | CORS for `:5173` | frontend | 0 | Done | `main.py` middleware |

### 13.6 Phase 5 — Deterministic Legal Graph (Weeks 15–18)

| ID | Feature | Category | Phase | Status | Notes |
|----|---------|----------|-------|--------|-------|
| 5.1.1 | Remove LLM graph extraction from worker | graph | 5 | Planned | `worker.py` — chunk+embed only |
| 5.1.2 | `settings.graph_extract_enabled = False` | graph | 5 | Planned | Default off |
| 5.2.1 | GDPR regex parser (`Art.`, `Abs.`) | graph | 5 | Planned | Deterministic nodes |
| 5.2.2 | BGB regex parser (`§`, Buch/Teil) | graph | 5 | Planned | Section hierarchy |
| 5.2.3 | DLG nodes: `law_article`, `law_section` | graph | 5 | Planned | Typed nodes |
| 5.2.4 | DLG edges: `CONTAINS`, `REFERENCES` | graph | 5 | Planned | Explicit citations |
| 5.2.5 | DLG storage in `graph_nodes`/`graph_edges` | graph | 5 | Planned | `document_id = NULL`, `source = gdpr` |
| 5.3.1 | Multi-hop query classifier (rules) | graph | 5 | Planned | "relationship", "compare articles" |
| 5.3.2 | DLG traversal 1–2 hops from seed | graph | 5 | Planned | After hybrid retrieve |
| 5.3.3 | Linked chunks into context window | graph | 5 | Planned | Before rerank |
| 5.3.4 | No LLM contract graph traversal | graph | 5 | Cancelled | Strategy decision |
| 5.4.1 | `GET .../graph-entities` returns DLG links | graph | 5 | Planned | Computed from cited articles |
| 5.4.2 | `GET /api/v1/corpus/graph` explorer | graph | 5 | Planned | GDPR/BGB structure tree |
| 5.5.1 | DLG populated for GDPR + BGB | graph | 5 | Planned | At law ingest |
| 5.5.2 | 10 multi-hop eval subset | eval | 5 | Planned | Improved context_recall |
| 5.5.3 | Contract LLM graph cancelled (unless 5b) | graph | 5 | Cancelled | Unless eval proves value |

### 13.7 Phase 6 — Agentic Workflows (Weeks 19–22)

| ID | Feature | Category | Phase | Status | Notes |
|----|---------|----------|-------|--------|-------|
| 6.1.1 | `services/agents/gap_analysis.py` | agent | 6 | Planned | Regulatory gap workflow |
| 6.1.2 | Obligation clause extraction (rules + LLM JSON) | agent | 6 | Planned | Structured output |
| 6.1.3 | Per-obligation hybrid law search | agent | 6 | Planned | `search_law` tool |
| 6.1.4 | Gap scoring: aligned/partial/missing | agent | 6 | Planned | Tabular report |
| 6.1.5 | `POST /api/v1/matters/{id}/gap-analysis` | agent | 6 | Planned | Returns `job_id` |
| 6.1.6 | `GET /api/v1/jobs/{job_id}` polling | agent | 6 | Planned | Redis progress key |
| 6.2.1 | Tool: `search_law` | agent | 6 | Planned | Hybrid, kind=law |
| 6.2.2 | Tool: `search_document` | agent | 6 | Planned | Hybrid, document_id |
| 6.2.3 | Tool: `get_article` | agent | 6 | Planned | DLG lookup |
| 6.2.4 | Tool: `cite_verify` | agent | 6 | Planned | Citation verifier |
| 6.2.5 | Fixed-sequence planner (no free ReAct) | agent | 6 | Planned | Max 5 LLM calls |
| 6.3.1 | `chat_sessions` table | agent | 6 | Planned | user_id, matter_id optional |
| 6.3.2 | `chat_messages` table | agent | 6 | Planned | role, content, sources JSONB |
| 6.3.3 | `GET /api/v1/chat/sessions` | agent | 6 | Planned | List sessions |
| 6.3.4 | `GET /api/v1/chat/sessions/{id}/messages` | agent | 6 | Planned | Message history |
| 6.3.5 | `DELETE /api/v1/chat/sessions/{id}` | agent | 6 | Planned | Session cleanup |
| 6.3.6 | Auto-create session on `POST /chat` | agent | 6 | Planned | If `session_id` provided |
| 6.4.1 | Gap analysis E2E test | eval | 6 | Planned | Full workflow |
| 6.4.2 | Chat history in UI | frontend | 6 | Planned | Phase 4 extension |
| 6.4.3 | Agent respects Ollama concurrency limit | agent | 6 | Planned | Semaphore(1) |

### 13.8 Phase 7 — Fine-Tuning Integration (Weeks 23–26)

| ID | Feature | Category | Phase | Status | Notes |
|----|---------|----------|-------|--------|-------|
| 7.1.1 | Training pairs `train_final.jsonl` (~94k) | fine-tune | 7 | Done | `data/processed/` |
| 7.1.2 | Eval pairs `eval_set.jsonl` (~10k) | fine-tune | 7 | Done | Held-out set |
| 7.1.3 | Colab notebook `phi35_legal_finetune.ipynb` | fine-tune | 7 | Partial | ~32% complete; GPU quota paused |
| 7.1.4 | `checkpoint_RESUME/` on Drive + local | fine-tune | 7 | Partial | Step ~3800 |
| 7.1.5 | GGUF export (Cell 8) | fine-tune | 7 | Planned | `ollama create` |
| 7.2.1 | Local smoke fine-tune (100 examples) | fine-tune | 7 | Done | `05_smoke_test_finetune.py` |
| 7.2.2 | QLoRA stack validation on 4050 | fine-tune | 7 | Done | Pipeline only; not production model |
| 7.3.1 | `ollama create jurisguard-v1` | fine-tune | 7 | Planned | From GGUF |
| 7.3.2 | `.env` `OLLAMA_MODEL=jurisguard-v1` | fine-tune | 7 | Planned | Swap inference model |
| 7.3.3 | Full RAGAS eval vs phi3.5 baseline | fine-tune | 7 | Planned | ≥ 3% faithfulness gain |
| 7.3.4 | Ship only if no latency regression | fine-tune | 7 | Planned | Phase 3 SLO gate |
| 7.4.1 | Fine-tune for legal tone / German style | fine-tune | 7 | Planned | Not retrieval |
| 7.4.2 | Fine-tune NOT for citation accuracy | fine-tune | 7 | Planned | Retrieval + verifier handles |
| 7.5.1 | `jurisguard-v1` on dev Ollama | fine-tune | 7 | Planned | Local verification |
| 7.5.2 | `eval/phi35_vs_jurisguard.json` | eval | 7 | Planned | Comparison report |
| 7.5.3 | `/api/v1/status` shows active model | fine-tune | 0 | Done | `configured_model` field |

### 13.9 Phase 8 — Enterprise Hardening (Weeks 27–30)

| ID | Feature | Category | Phase | Status | Notes |
|----|---------|----------|-------|--------|-------|
| 8.1.1 | BDSG corpus ingest | ops | 8 | Planned | ~200 chunks |
| 8.1.2 | EU AI Act excerpts | ops | 8 | Planned | ~150 chunks |
| 8.1.3 | Internal contract playbooks | ops | 8 | Planned | Org-specific |
| 8.1.4 | ePrivacy Directive | ops | 8 | Deferred | ~100 chunks |
| 8.1.5 | `jurisdiction: DE\|EU` metadata | RAG | 8 | Planned | Filter by jurisdiction |
| 8.2.1 | Row-level `org_id` on matters | security | 8 | Planned | Multi-tenant isolation |
| 8.2.2 | `org_id` on document_chunks (via matter) | security | 8 | Planned | Retrieval scoping |
| 8.2.3 | `org_id` on audit_events | security | 8 | Planned | Audit isolation |
| 8.2.4 | Postgres RLS policies (optional) | security | 8 | Deferred | Defense-in-depth |
| 8.3.1 | structlog JSON API logs | ops | 8 | Planned | Structured logging |
| 8.3.2 | `query_traces` table (lite flight recorder) | ops | 8 | Planned | Port V1 concept |
| 8.3.3 | Prometheus `/metrics` | ops | 8 | Planned | Per-stage latency histograms |
| 8.3.4 | Sentry integration (optional) | ops | 8 | Deferred | Error tracking |
| 8.4.1 | Offline install documentation | ops | 8 | Planned | USB bundle procedure |
| 8.4.2 | `scripts/airgap_bundle.sh` | ops | 8 | Planned | Models + corpus + images |
| 8.5.1 | OWASP LLM Top 10 checklist | security | 8 | Planned | Security audit |
| 8.5.2 | `pip-audit` dependency scan | security | 8 | Planned | Python CVEs |
| 8.5.3 | `npm audit` (frontend) | security | 8 | Planned | JS CVEs |
| 8.5.4 | Pen test on RBAC + injection suite | security | 8 | Planned | External or internal |
| 8.6.1 | BDSG in corpus; stats updated | ops | 8 | Planned | `GET /corpus/stats` |
| 8.6.2 | Air-gap install runbook | ops | 8 | Planned | Enterprise deployment |

### 13.10 Phase 9 — Rebrand, Migration & GTM (Weeks 31–34)

| ID | Feature | Category | Phase | Status | Notes |
|----|---------|----------|-------|--------|-------|
| 9.1.1 | Repo rename `jurisguard` / `jurisguard-platform` | rebrand | 9 | Planned | GitHub + local |
| 9.1.2 | Promote `v2/` to repo root | rebrand | 9 | Planned | `backend/`, `frontend/` at top |
| 9.1.3 | `legacy/v1/` archive | rebrand | 9 | Planned | BEWEIS read-only |
| 9.2.1 | Remove port 8001 V1 conflict | rebrand | 9 | Planned | Single compose |
| 9.2.2 | CI paths v2-only | rebrand | 9 | Planned | No V1 jobs |
| 9.3.1 | Pitch deck with verified Phase 3 metrics | rebrand | 9 | Planned | No fabricated claims |
| 9.3.2 | 30-minute Docker demo script | rebrand | 9 | Planned | Sales enablement |
| 9.3.3 | DPO one-pager (data flow, on-prem) | rebrand | 9 | Planned | Procurement doc |
| 9.4.1 | Tabular review (Legora-style) | frontend | 10+ | Deferred | N-document grid |
| 9.4.2 | SSO (OIDC/SAML) | security | 10+ | Deferred | Enterprise procurement |
| 9.4.3 | DOCX/PDF redlining export | frontend | 10+ | Deferred | Track changes |
| 9.4.4 | DMS integrations (iManage, SharePoint) | ops | 11+ | Deferred | Connector layer |
| 9.4.5 | Multi-language UI (DE/EN) | frontend | 10+ | Deferred | i18n |
| 9.4.6 | Private cloud Helm chart | ops | 11+ | Deferred | K8s deployment |

### 13.11 Cross-Category Summary Matrix

| Category | Done | Partial | Planned | Cancelled | Deferred | Total |
|----------|------|---------|---------|-----------|----------|-------|
| **bugs** | 6 | 1 | 4 | 0 | 0 | 11 |
| **security** | 1 | 0 | 28 | 0 | 2 | 31 |
| **RAG** | 2 | 0 | 24 | 0 | 0 | 26 |
| **graph** | 0 | 1 | 14 | 3 | 0 | 18 |
| **agent** | 0 | 0 | 17 | 0 | 0 | 17 |
| **eval** | 1 | 0 | 28 | 0 | 0 | 29 |
| **frontend** | 1 | 0 | 14 | 0 | 3 | 18 |
| **fine-tune** | 4 | 2 | 7 | 0 | 0 | 13 |
| **ops** | 8 | 0 | 18 | 0 | 3 | 29 |
| **rebrand** | 0 | 0 | 9 | 0 | 0 | 9 |
| **TOTAL** | **23** | **4** | **163** | **3** | **8** | **201** |

### 13.12 Critical Path Items (MVP for Pilots)

These items gate the minimum viable product for pilot customers (Phase 0 → 1 → 2 → 3 → 4 → 9):

| Priority | ID | Item | Blocking |
|----------|-----|------|----------|
| P0 | 0.2.1 | Models on disk | Cold latency 3–7 min |
| P0 | 1.2.4 | Retrieval-layer RBAC | Enterprise sales |
| P0 | 1.7.1 | Audit read API | DPO procurement |
| P0 | 2.1.3 | Hybrid search | Retrieval quality |
| P0 | 2.5.1 | Confidence gate | Hallucination risk |
| P0 | 3.5.2 | RAGAS baseline | Marketing claims |
| P0 | 4.2.1–4.2.4 | Core frontend pages | Non-dev usability |
| P0 | 9.3.1 | Verified metrics deck | GTM integrity |

---

## Part 14 — Phase Dependency Graph & 34-Week Gantt Timeline

### 14.1 Phase Dependency Graph

```mermaid
flowchart TB
    P0["Phase 0<br/>Stabilization<br/>Week 1"]
    P1["Phase 1<br/>Security & RBAC<br/>Weeks 2–4"]
    P2["Phase 2<br/>Retrieval Upgrade<br/>Weeks 5–8"]
    P3["Phase 3<br/>Eval & CI<br/>Weeks 9–10"]
    P4["Phase 4<br/>Frontend<br/>Weeks 11–14"]
    P5["Phase 5<br/>DLG Graph<br/>Weeks 15–18"]
    P6["Phase 6<br/>Agents<br/>Weeks 19–22"]
    P7["Phase 7<br/>Fine-Tune<br/>Weeks 23–26"]
    P8["Phase 8<br/>Enterprise<br/>Weeks 27–30"]
    P9["Phase 9<br/>Rebrand & GTM<br/>Weeks 31–34"]

    P0 --> P1
    P1 --> P2
    P2 --> P3
    P3 --> P4
    P4 --> P9
    P2 --> P5
    P5 --> P6
    P3 -.-> P7
    P7 -.-> P8
    P6 --> P8
    P8 --> P9

    style P0 fill:#e8f5e9
    style P1 fill:#fff3e0
    style P2 fill:#e3f2fd
    style P3 fill:#fce4ec
    style P4 fill:#f3e5f5
    style P9 fill:#ffebee
```

### 14.2 Dependency Rules

| Rule | Description |
|------|-------------|
| **Hard: 0 → 1** | RBAC requires stable Docker, worker, and model paths |
| **Hard: 1 → 2** | Retrieval filters need user/doc access model |
| **Hard: 2 → 3** | Eval measures retrieval changes; baseline requires hybrid |
| **Hard: 3 → 4** | UI must not ship unverified accuracy claims |
| **Hard: 4 → 9** | GTM requires usable product (frontend) |
| **Soft: 2 → 5** | DLG builds on re-ingested law corpus from Phase 2 |
| **Soft: 5 → 6** | Agents use DLG `get_article` tool |
| **Parallel: 7** | Colab fine-tune runs anytime; integration after Phase 3 baselines |
| **Soft: 6,7 → 8** | Enterprise hardening absorbs agent + fine-tune outputs |
| **Anti: 5 before 2** | Graph traversal without hybrid retrieval amplifies bad recall |
| **Anti: 6 before 3** | Agents without eval baseline cannot be trusted |
| **Anti: 7 before 2** | Fine-tuning does not fix retrieval; wrong investment order |

### 14.3 Critical Path (MVP Pilots)

```
Week 1:   Phase 0 — stabilize
Weeks 2–4: Phase 1 — RBAC + audit API
Weeks 5–8: Phase 2 — hybrid RAG
Weeks 9–10: Phase 3 — RAGAS baseline
Weeks 11–14: Phase 4 — React frontend
Weeks 31–34: Phase 9 — rebrand + GTM
```

**Duration:** 22 weeks on critical path (with overlap: ~26 weeks elapsed including Phase 0 buffer).

### 14.4 Secondary Paths

| Path | Phases | Duration | When to start |
|------|--------|----------|---------------|
| **Graph path** | 5 → 6 | 8 weeks | After Phase 2+3 prove vector pipeline |
| **Fine-tune path** | 7 (parallel) | 4 weeks integration | Colab anytime; swap after Phase 3 |
| **Enterprise path** | 8 | 4 weeks | After Phase 6 or in parallel with Phase 7 |

### 14.5 34-Week Gantt Chart (Mermaid)

```mermaid
gantt
    title JurisGuard 34-Week Master Timeline (June 2026 – January 2027)
    dateFormat YYYY-MM-DD
    axisFormat %b %d

    section Phase 0
    Stabilization & assets           :p0, 2026-06-16, 1w
    E2E CI + runbook                   :p0b, after p0, 1w

    section Phase 1
    RBAC schema migration              :p1a, 2026-06-30, 2w
    Admin API + rate limits            :p1b, after p1a, 1w
    Audit read API + injection L2      :p1c, after p1a, 2w

    section Phase 2
    Hybrid BM25+vector+RRF             :p2a, 2026-07-28, 2w
    HyDE + structure chunking          :p2b, after p2a, 2w
    Citation verifier + confidence     :p2c, after p2b, 2w

    section Phase 3
    Golden dataset + RAGAS             :p3, 2026-09-08, 2w

    section Phase 4
    Auth + chat UI                     :p4a, 2026-09-22, 2w
    Matters + upload + analyze         :p4b, after p4a, 2w

    section Phase 5
    Stop LLM graph + build DLG         :p5a, 2026-10-20, 2w
    Graph-augmented retrieval          :p5b, after p5a, 2w

    section Phase 6
    Gap analysis agent                 :p6a, 2026-11-17, 2w
    Chat history API + UI              :p6b, after p6a, 2w

    section Phase 7
    Colab fine-tune (parallel)         :p7a, 2026-09-08, 12w
    GGUF export + Ollama swap          :p7b, 2026-12-15, 2w
    RAGAS comparison report            :p7c, after p7b, 2w

    section Phase 8
    BDSG corpus + multi-tenant         :p8a, 2027-01-12, 2w
    Observability + air-gap bundle     :p8b, after p8a, 2w

    section Phase 9
    Repo restructure + V1 archive      :p9a, 2027-02-09, 2w
    GTM materials + demo script        :p9b, after p9a, 2w
```

### 14.6 Week-by-Week Task Table

| Week | Dates (2026–2027) | Phase | Primary deliverables | Dependencies |
|------|-------------------|-------|----------------------|--------------|
| 1 | Jun 16–22 | 0 | Verify assets, E2E 27/27, orphan cleanup | — |
| 2 | Jun 23–29 | 1 | Alembic 004 RBAC schema draft | Phase 0 |
| 3 | Jun 30–Jul 6 | 1 | `require_matter_access`, retrieval filter | 004 schema |
| 4 | Jul 7–13 | 1 | Admin router, rate limits, audit API | RBAC deps |
| 5 | Jul 14–20 | 2 | Alembic 005 tsvector + GIN index | Phase 1 |
| 6 | Jul 21–27 | 2 | `hybrid_search()` SQL + backfill | 005 migration |
| 7 | Jul 28–Aug 3 | 2 | Wire hybrid into `rag.py` | hybrid_search |
| 8 | Aug 4–10 | 2 | HyDE flag, structure chunking, re-ingest | hybrid live |
| 9 | Aug 11–17 | 2 | Citation verifier, confidence gate | rerank scores |
| 10 | Aug 18–24 | 3 | Golden set v1 (50 law + 20 contract) | Phase 2 |
| 11 | Aug 25–31 | 3 | RAGAS script + `eval/baseline.json` | golden set |
| 12 | Sep 1–7 | 3 | Logical eval + latency benchmarks | RAGAS |
| 13 | Sep 8–14 | 4 | React scaffold, login, chat page | Phase 3 baseline |
| 14 | Sep 15–21 | 4 | Matters list/create, upload flow | auth UI |
| 15 | Sep 22–28 | 4 | Analyze, compare, source panel | matters UI |
| 16 | Sep 29–Oct 5 | 4 | Admin, audit, settings pages | Phase 1 APIs |
| 17 | Oct 6–12 | 4 | Playwright smoke + polish | all pages |
| 18 | Oct 13–19 | 5 | Disable LLM graph extraction | Phase 4 |
| 19 | Oct 20–26 | 5 | DLG parser for GDPR/BGB | law re-ingest |
| 20 | Oct 27–Nov 2 | 5 | DLG edges + corpus graph API | DLG nodes |
| 21 | Nov 3–9 | 5 | Multi-hop classifier + traversal | DLG populated |
| 22 | Nov 10–16 | 5 | DLG eval subset (10 questions) | traversal live |
| 23 | Nov 17–23 | 6 | Gap analysis agent + job queue | Phase 5 |
| 24 | Nov 24–30 | 6 | Tool registry + gap E2E | agent service |
| 25 | Dec 1–7 | 6 | Chat sessions/messages tables | — |
| 26 | Dec 8–14 | 6 | Chat history API + UI integration | tables |
| 27 | Dec 15–21 | 7 | GGUF export + `jurisguard-v1` Ollama | Colab complete |
| 28 | Dec 22–28 | 7 | RAGAS phi3.5 vs jurisguard-v1 | model swap |
| 29 | Dec 29–Jan 4 | 7 | Ship decision + status endpoint update | eval report |
| 30 | Jan 5–11 | 8 | BDSG ingest + jurisdiction metadata | — |
| 31 | Jan 12–18 | 8 | Multi-tenant org_id + Prometheus | BDSG |
| 32 | Jan 19–25 | 8 | Air-gap bundle + security audit | observability |
| 33 | Jan 26–Feb 1 | 9 | Repo restructure, V1 → `legacy/` | Phase 8 |
| 34 | Feb 2–8 | 9 | Pitch deck, demo script, DPO one-pager | verified metrics |

### 14.7 Milestone Gates

| Milestone | Week | Gate criteria | Go/No-Go |
|-----------|------|---------------|----------|
| **M0: Stable API** | 1 | E2E 27/27; models on disk; worker processes uploads | Must pass |
| **M1: Enterprise trust** | 4 | RBAC retrieval test; audit API; rate limits | Must pass for pilots |
| **M2: Quality RAG** | 9 | Hybrid live; faithfulness ≥ baseline − 5% | Must pass |
| **M3: Measurable** | 12 | `eval/baseline.json` committed; p95 documented | Must pass for GTM |
| **M4: Usable product** | 17 | Playwright smoke green; 4 core pages | Must pass for demos |
| **M5: Graph value** | 22 | 10 multi-hop questions: context_recall +10% | Optional; cancel graph if fail |
| **M6: Agent value** | 26 | Gap analysis E2E on sample NDA | Optional for MVP |
| **M7: Model swap** | 29 | jurisguard-v1 faithfulness ≥ phi3.5 + 3% | Optional |
| **M8: Enterprise ready** | 32 | BDSG ingested; air-gap runbook; OWASP checklist | Must pass for enterprise |
| **M9: Market ready** | 34 | Rebrand complete; deck with real numbers only | Launch gate |

### 14.8 Resource Allocation (Solo / Part-Time)

| Phase | Effort (person-weeks) | Parallelizable | Notes |
|-------|----------------------|----------------|-------|
| 0 | 1 | No | Blocking for all |
| 1 | 3 | Partial | Schema first, then API |
| 2 | 5 | Partial | Hybrid before HyDE |
| 3 | 2 | No | Needs stable RAG |
| 4 | 5 | Partial | UI pages parallelizable |
| 5 | 4 | Partial | Parser before traversal |
| 6 | 4 | Partial | Agent after DLG |
| 7 | 4 (+ Colab wall time) | Yes | Colab runs unattended |
| 8 | 4 | Partial | Corpus + ops parallel |
| 9 | 2 | No | Final polish |
| **Total** | **34** | | ~8 months part-time |

### 14.9 Compression Scenarios

| Scenario | Compressed timeline | Trade-offs |
|----------|---------------------|------------|
| **Full-time solo** | 20–24 weeks | Phases 4+5 overlap; Phase 7 Colab parallel |
| **MVP-only** | 14 weeks (0→1→2→3→4) | Skip graph, agents, fine-tune, enterprise |
| **Enterprise-first** | 18 weeks | Phase 1+2+8 before frontend; UI last |
| **Demo-only** | 10 weeks | Phase 0+2+4 minimal; no RBAC; not sellable |

---

## Part 15 — API & Schema Reference Appendix

### 15.1 API Overview

| Property | Value |
|----------|-------|
| **Base URL (dev)** | `http://localhost:8002` |
| **API prefix** | `/api/v1` |
| **OpenAPI** | `GET /docs`, `GET /openapi.json` |
| **Auth** | Bearer JWT (`Authorization: Bearer <token>`) |
| **Content-Type** | `application/json` (except multipart upload) |
| **Current paths (shipped)** | 16 OpenAPI paths |
| **E2E pass rate** | 27/27 (`scripts/e2e_functional_test.py`) |

### 15.2 Infrastructure Endpoints (`main.py`)

#### `GET /health`

| Field | Value |
|-------|-------|
| **Auth** | None |
| **Purpose** | Liveness probe; DB ping on startup |

**Response 200:**

```json
{
  "status": "ok",
  "service": "JurisGuard V2",
  "phase": "2.2-3"
}
```

#### `GET /api/v1/status`

| Field | Value |
|-------|-------|
| **Auth** | None |
| **Purpose** | System diagnostics: Ollama, training manifest, DB |

**Response 200:**

```json
{
  "ollama": {
    "base_url": "http://localhost:11434",
    "configured_model": "phi3.5",
    "reachable": true,
    "models": ["phi3.5:latest"]
  },
  "training": {
    "dir": "/training",
    "manifest": { "last_step": 3800, "status": "paused" },
    "resume_checkpoint_exists": true
  },
  "database": "localhost:5433/juris_db",
  "phase": "2.2-auth, 2.3-corpus, 3-rag"
}
```

#### `GET /docs` / `GET /openapi.json`

| Field | Value |
|-------|-------|
| **Auth** | None |
| **Purpose** | Swagger UI and machine-readable OpenAPI 3.x spec |

---

### 15.3 Auth Router (`routers/auth.py`)

Prefix: `/api/v1/auth`

#### `POST /api/v1/auth/register`

| Field | Value |
|-------|-------|
| **Auth** | None |
| **Request body** | `RegisterRequest` |
| **Response** | `TokenResponse` |
| **Errors** | 409 (email exists), 400 (password policy) |

**Request:**

```json
{
  "email": "dpo@firm.example",
  "password": "SecurePass123!"
}
```

| Field | Type | Constraints |
|-------|------|-------------|
| `email` | string (EmailStr) | Valid email format |
| `password` | string | min 8, max 128 chars |

**Response 200:**

```json
{
  "access_token": "eyJhbGciOiJIUzI1NiIs...",
  "token_type": "bearer"
}
```

**Planned (Phase 1):** optional `org_name` field — first user creates organization.

#### `POST /api/v1/auth/login`

| Field | Value |
|-------|-------|
| **Auth** | None |
| **Request body** | `LoginRequest` |
| **Response** | `TokenResponse` |
| **Errors** | 401 (invalid credentials) |
| **Planned rate limit** | 5/min/IP (Phase 1) |

**Request:**

```json
{
  "email": "dpo@firm.example",
  "password": "SecurePass123!"
}
```

#### `GET /api/v1/auth/me`

| Field | Value |
|-------|-------|
| **Auth** | Bearer JWT required |
| **Response** | `UserResponse` |
| **Errors** | 401 (missing/invalid token) |

**Response 200:**

```json
{
  "id": "550e8400-e29b-41d4-a716-446655440000",
  "email": "dpo@firm.example",
  "created_at": "2026-06-01T10:00:00Z"
}
```

**Planned (Phase 1):** add `role`, `org_id` to response.

---

### 15.4 Chat Router (`routers/chat.py`)

Prefix: `/api/v1/chat`

#### `POST /api/v1/chat`

| Field | Value |
|-------|-------|
| **Auth** | Bearer JWT required |
| **Request body** | `ChatRequest` |
| **Response** | `ChatResponse` |
| **Errors** | 400 (injection/length), 401, 503 (ML unavailable) |
| **Planned rate limit** | 10/min/user (Phase 1) |
| **Pipeline** | embed → pgvector search → rerank → Ollama generate |

**Request:**

```json
{
  "message": "What lawful bases exist under GDPR Article 6?",
  "use_law_corpus": true
}
```

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `message` | string | required | min 1, max 8000 chars |
| `use_law_corpus` | boolean | `true` | Filter `metadata.kind == "law"` |

**Planned fields (Phase 2/6):**

| Field | Phase | Description |
|-------|-------|-------------|
| `use_hyde` | 2 | Enable HyDE hypothetical document embedding |
| `session_id` | 6 | Attach to chat session for history |

**Response 200:**

```json
{
  "answer": "Under GDPR Article 6, lawful processing requires one of six bases...",
  "model": "phi3.5",
  "sources": [
    {
      "label": "GDPR Art. 6(1) Lawfulness",
      "source": "gdpr",
      "distance": 0.234
    }
  ]
}
```

**Injection rejection (400):**

```json
{
  "detail": "Query rejected due to potential prompt injection or excessive length."
}
```

**Planned endpoints (Phase 6):**

| Method | Path | Description |
|--------|------|-------------|
| `GET` | `/api/v1/chat/sessions` | List user chat sessions |
| `GET` | `/api/v1/chat/sessions/{id}/messages` | Session message history |
| `DELETE` | `/api/v1/chat/sessions/{id}` | Delete session |

---

### 15.5 Corpus Router (`routers/corpus.py`)

Prefix: `/api/v1/corpus`

#### `GET /api/v1/corpus/stats`

| Field | Value |
|-------|-------|
| **Auth** | None (public in E2E; may require auth in Phase 1) |
| **Response** | `CorpusStatsResponse` |
| **Source** | `services/vector_store.corpus_stats()` |

**Response 200 (verified June 2026):**

```json
{
  "total_chunks": 1862,
  "by_source": {
    "gdpr": 293,
    "bgb": 1565,
    "contract": 4
  }
}
```

#### `POST /api/v1/corpus/ingest-law`

| Field | Value |
|-------|-------|
| **Auth** | Bearer JWT required |
| **Purpose** | Returns CLI instructions (not inline ingest) |
| **Reason** | Heavy CPU job; avoids API timeout |

**Response 200:**

```json
{
  "message": "Run law ingest with: docker compose exec api python /app/src/ingest_law.py",
  "note": "Heavy CPU job; not run inline to avoid API timeout."
}
```

**Planned (Phase 5):**

| Method | Path | Description |
|--------|------|-------------|
| `GET` | `/api/v1/corpus/graph` | DLG structure tree explorer |

---

### 15.6 Matters Router (`routers/matters.py`)

Prefix: `/api/v1/matters`

All endpoints require Bearer JWT. Matters are user-scoped (`Matter.user_id == current_user.id`).

#### `POST /api/v1/matters`

| Field | Value |
|-------|-------|
| **Request body** | `MatterCreate` |
| **Response** | `MatterResponse` |
| **Side effect** | `AuditEvent` action=`create` |

**Request:**

```json
{
  "name": "Acme NDA Review",
  "description": "Q2 2026 vendor NDA"
}
```

**Response 200:**

```json
{
  "id": "a1b2c3d4-e5f6-7890-abcd-ef1234567890",
  "user_id": "550e8400-e29b-41d4-a716-446655440000",
  "name": "Acme NDA Review",
  "description": "Q2 2026 vendor NDA",
  "created_at": "2026-06-15T14:30:00Z"
}
```

#### `GET /api/v1/matters`

| Field | Value |
|-------|-------|
| **Response** | `list[MatterResponse]` |
| **Filter** | Current user's matters only |

#### `GET /api/v1/matters/{matter_id}`

| Field | Value |
|-------|-------|
| **Response** | `MatterResponse` |
| **Errors** | 404 (not found or not owned) |

#### `DELETE /api/v1/matters/{matter_id}`

| Field | Value |
|-------|-------|
| **Response** | `{"ok": true}` |
| **Cascade** | GraphEdges → GraphNodes → DocumentChunks → MatterDocuments → Matter |
| **Side effect** | `AuditEvent` action=`delete` |

#### `POST /api/v1/matters/{matter_id}/documents`

| Field | Value |
|-------|-------|
| **Content-Type** | `multipart/form-data` |
| **Field** | `file` (UploadFile) |
| **Response** | `DocumentUploadResponse` |
| **Side effect** | Celery `process_document_task.delay(doc_id)` |
| **Storage** | `data/uploads/{matter_id}/{filename}` |
| **Planned rate limit** | 5/hour/user (Phase 1) |

**Response 200:**

```json
{
  "id": "doc-uuid-here",
  "matter_id": "matter-uuid-here",
  "filename": "nda_acme.pdf",
  "file_path": "/app/data/uploads/matter-uuid/nda_acme.pdf",
  "uploaded_at": "2026-06-15T14:35:00Z"
}
```

#### `GET /api/v1/matters/{matter_id}/documents/{document_id}/status`

| Field | Value |
|-------|-------|
| **Response** | `{"status": "processing"}` or `{"status": "processed"}` |
| **Logic** | `processed` if `DocumentChunk` count > 0 for document_id |

#### `GET /api/v1/matters/{matter_id}/documents/{document_id}/graph-entities`

| Field | Value |
|-------|-------|
| **Response** | `{"entities": [...]}` |
| **Source** | `graph_nodes` table (LLM-extracted; unreliable) |
| **Phase 5 change** | Returns DLG nodes linked to cited articles |

**Response 200:**

```json
{
  "entities": [
    {
      "id": "node-uuid",
      "name": "Acme Corp",
      "type": "ORGANIZATION",
      "description": "Party to the agreement"
    }
  ]
}
```

#### `GET /api/v1/matters/{matter_id}/documents/{document_id}/graph-edges`

| Field | Value |
|-------|-------|
| **Response** | `{"edges": [...]}` |

**Response 200:**

```json
{
  "edges": [
    {
      "id": "edge-uuid",
      "source": "source-node-uuid",
      "target": "target-node-uuid",
      "type": "PARTY_TO"
    }
  ]
}
```

#### `POST /api/v1/matters/{matter_id}/analyze`

| Field | Value |
|-------|-------|
| **Request body** | `DocumentAnalysisRequest` |
| **Response** | `DocumentAnalysisResponse` |
| **RAG scope** | `document_id` only (`use_law_corpus=false`) |
| **Side effect** | `AuditEvent` action=`analyze` |

**Request:**

```json
{
  "document_id": "doc-uuid-here",
  "question": "What is the confidentiality period in this NDA?"
}
```

**Response 200:**

```json
{
  "document_id": "doc-uuid-here",
  "question": "What is the confidentiality period in this NDA?",
  "answer": "The confidentiality obligation extends for 3 years...",
  "model": "phi3.5",
  "sources": [
    {
      "label": "chunk-42",
      "source": null,
      "distance": 0.189
    }
  ]
}
```

#### `POST /api/v1/matters/{matter_id}/compare`

| Field | Value |
|-------|-------|
| **Request body** | `DocumentCompareRequest` |
| **Response** | `DocumentCompareResponse` |
| **Pipeline** | Two sequential RAG calls: doc-scoped + law corpus |
| **Side effect** | `AuditEvent` action=`compare` |

**Request:**

```json
{
  "document_id": "doc-uuid-here"
}
```

**Response 200:**

```json
{
  "document_id": "doc-uuid-here",
  "comparison_result": "## Document analysis\n...\n\n## Regulatory baseline (GDPR/BGB)\n...",
  "model": "phi3.5"
}
```

**Planned (Phase 1):**

| Method | Path | Description |
|--------|------|-------------|
| `POST` | `/api/v1/matters/{id}/members` | Invite collaborator |
| `DELETE` | `/api/v1/matters/{id}/members/{user_id}` | Remove member |

**Planned (Phase 6):**

| Method | Path | Description |
|--------|------|-------------|
| `POST` | `/api/v1/matters/{id}/gap-analysis` | Start regulatory gap analysis job |
| `GET` | `/api/v1/jobs/{job_id}` | Poll job status |

---

### 15.7 Planned Admin Router (`routers/admin.py` — Phase 1)

Prefix: `/api/v1/admin`

| Method | Path | Auth role | Description |
|--------|------|-----------|-------------|
| `GET` | `/users` | `org_admin`, `owner` | List org users |
| `PUT` | `/users/{id}/role` | `owner` | Change user role |
| `DELETE` | `/users/{id}` | `owner` | Deactivate/delete user |

---

### 15.8 Planned Audit Router (Phase 1)

Prefix: `/api/v1/audit`

| Method | Path | Auth role | Query params | Description |
|--------|------|-----------|--------------|-------------|
| `GET` | `/` | `org_admin`+ | `user_id`, `action`, `resource_type`, `from`, `to`, `page` | Paginated audit log |
| `GET` | `/export` | `org_admin`+ | same filters | CSV download |

**AuditEvent fields (write-only today):**

| Field | Type | Description |
|-------|------|-------------|
| `id` | UUID | Primary key |
| `user_id` | UUID FK → users | Actor |
| `action` | string | `create`, `upload`, `analyze`, `compare`, `delete` |
| `resource_type` | string | `matter`, `document` |
| `resource_id` | string | Target resource ID |
| `timestamp` | timestamptz | Event time |
| `details` | JSONB | Context (filename, question, etc.) |

---

### 15.9 Complete Endpoint Index

| # | Method | Path | Auth | Status | Phase |
|---|--------|------|------|--------|-------|
| 1 | GET | `/health` | No | Shipped | 0 |
| 2 | GET | `/api/v1/status` | No | Shipped | 0 |
| 3 | GET | `/docs` | No | Shipped | 0 |
| 4 | GET | `/openapi.json` | No | Shipped | 0 |
| 5 | POST | `/api/v1/auth/register` | No | Shipped | 0 |
| 6 | POST | `/api/v1/auth/login` | No | Shipped | 0 |
| 7 | GET | `/api/v1/auth/me` | Yes | Shipped | 0 |
| 8 | POST | `/api/v1/chat` | Yes | Shipped | 0 |
| 9 | GET | `/api/v1/corpus/stats` | No | Shipped | 0 |
| 10 | POST | `/api/v1/corpus/ingest-law` | Yes | Shipped | 0 |
| 11 | POST | `/api/v1/matters` | Yes | Shipped | 0 |
| 12 | GET | `/api/v1/matters` | Yes | Shipped | 0 |
| 13 | GET | `/api/v1/matters/{matter_id}` | Yes | Shipped | 0 |
| 14 | DELETE | `/api/v1/matters/{matter_id}` | Yes | Shipped | 0 |
| 15 | POST | `/api/v1/matters/{matter_id}/documents` | Yes | Shipped | 0 |
| 16 | GET | `/api/v1/matters/{matter_id}/documents/{document_id}/status` | Yes | Shipped | 0 |
| 17 | GET | `/api/v1/matters/{matter_id}/documents/{document_id}/graph-entities` | Yes | Shipped | 0 |
| 18 | GET | `/api/v1/matters/{matter_id}/documents/{document_id}/graph-edges` | Yes | Shipped | 0 |
| 19 | POST | `/api/v1/matters/{matter_id}/analyze` | Yes | Shipped | 0 |
| 20 | POST | `/api/v1/matters/{matter_id}/compare` | Yes | Shipped | 0 |
| 21 | GET | `/api/v1/audit` | Yes | Planned | 1 |
| 22 | GET | `/api/v1/audit/export` | Yes | Planned | 1 |
| 23 | GET | `/api/v1/admin/users` | Yes | Planned | 1 |
| 24 | PUT | `/api/v1/admin/users/{id}/role` | Yes | Planned | 1 |
| 25 | DELETE | `/api/v1/admin/users/{id}` | Yes | Planned | 1 |
| 26 | POST | `/api/v1/matters/{id}/members` | Yes | Planned | 1 |
| 27 | DELETE | `/api/v1/matters/{id}/members/{user_id}` | Yes | Planned | 1 |
| 28 | GET | `/api/v1/corpus/graph` | Yes | Planned | 5 |
| 29 | POST | `/api/v1/matters/{id}/gap-analysis` | Yes | Planned | 6 |
| 30 | GET | `/api/v1/jobs/{job_id}` | Yes | Planned | 6 |
| 31 | GET | `/api/v1/chat/sessions` | Yes | Planned | 6 |
| 32 | GET | `/api/v1/chat/sessions/{id}/messages` | Yes | Planned | 6 |
| 33 | DELETE | `/api/v1/chat/sessions/{id}` | Yes | Planned | 6 |
| 34 | GET | `/metrics` | No | Planned | 8 |

### 15.10 Database Schema (`db.py` + Alembic)

**Engine:** PostgreSQL 16 + `pgvector` extension  
**ORM:** SQLAlchemy 2.x async (`asyncpg` driver)  
**Migrations:** Alembic (`backend/alembic/versions/`)

#### Extension

```sql
CREATE EXTENSION IF NOT EXISTS vector;
```

#### Table: `users`

| Column | Type | Constraints | ORM model |
|--------|------|-------------|-----------|
| `id` | UUID | PK, default `gen_random_uuid()` | `User.id` |
| `email` | VARCHAR(255) / TEXT | UNIQUE, NOT NULL | `User.email` |
| `password_hash` | VARCHAR(255) / TEXT | NOT NULL | `User.password_hash` |
| `created_at` | TIMESTAMPTZ | DEFAULT NOW() | `User.created_at` |

**Planned (Phase 1):**

| Column | Type | Description |
|--------|------|-------------|
| `role` | VARCHAR(20) | `member`, `matter_lead`, `org_admin`, `owner` |
| `org_id` | UUID FK | References `organizations.id` |

#### Table: `document_chunks`

| Column | Type | Constraints | ORM model |
|--------|------|-------------|-----------|
| `id` | BIGSERIAL | PK | `DocumentChunk.id` |
| `document_id` | UUID | NOT NULL, indexed | `DocumentChunk.document_id` |
| `chunk_index` | INT | NOT NULL | `DocumentChunk.chunk_index` |
| `content` | TEXT | NOT NULL | `DocumentChunk.content` |
| `embedding` | vector(1024) | pgvector; not in ORM | Raw SQL insert |
| `metadata` | JSONB | DEFAULT `{}` | `DocumentChunk.metadata_` |
| `created_at` | TIMESTAMPTZ | DEFAULT NOW() | Migration 001 |

**Indexes:**

| Index | Type | Column(s) |
|-------|------|-----------|
| `idx_document_chunks_document_id` | B-tree | `document_id` |
| HNSW (post-ingest) | HNSW | `embedding` |

**Planned (Phase 2):**

| Column | Type | Description |
|--------|------|-------------|
| `content_tsv` | tsvector | Full-text search; GIN indexed |

**Metadata JSONB conventions:**

| Key | Values | Used by |
|-----|--------|---------|
| `kind` | `law`, `contract` | RAG filter |
| `source` | `gdpr`, `bgb`, `bdsg` | Corpus stats |
| `title` | string | Source label in chat |
| `article` | string | Phase 2 structure chunking |
| `paragraph` | string | Phase 2 structure chunking |
| `document_id` | UUID string | Matter document scope |
| `parent_chunk_id` | int | Phase 2 parent-child |
| `jurisdiction` | `DE`, `EU` | Phase 8 corpus expansion |

#### Table: `matters`

| Column | Type | Constraints | ORM model |
|--------|------|-------------|-----------|
| `id` | UUID | PK | `Matter.id` |
| `user_id` | UUID | FK → users, NOT NULL | `Matter.user_id` |
| `name` | VARCHAR | NOT NULL | `Matter.name` |
| `description` | TEXT | nullable | `Matter.description` |
| `created_at` | TIMESTAMPTZ | DEFAULT NOW() | `Matter.created_at` |

**Planned (Phase 1/8):**

| Column | Type | Description |
|--------|------|-------------|
| `org_id` | UUID FK | Multi-tenant isolation |

#### Table: `matter_documents`

| Column | Type | Constraints | ORM model |
|--------|------|-------------|-----------|
| `id` | UUID | PK | `MatterDocument.id` |
| `matter_id` | UUID | FK → matters, NOT NULL | `MatterDocument.matter_id` |
| `filename` | VARCHAR | NOT NULL | `MatterDocument.filename` |
| `file_path` | VARCHAR | NOT NULL | `MatterDocument.file_path` |
| `uploaded_at` | TIMESTAMPTZ | DEFAULT NOW() | `MatterDocument.uploaded_at` |

**Planned (Phase 1):**

| Column | Type | Description |
|--------|------|-------------|
| `confidentiality` | VARCHAR(20) | `internal`, `restricted`, `privileged` |

#### Table: `audit_events`

| Column | Type | Constraints | ORM model |
|--------|------|-------------|-----------|
| `id` | UUID | PK | `AuditEvent.id` |
| `user_id` | UUID | FK → users | `AuditEvent.user_id` |
| `action` | VARCHAR | NOT NULL | `AuditEvent.action` |
| `resource_type` | VARCHAR | NOT NULL | `AuditEvent.resource_type` |
| `resource_id` | VARCHAR | nullable | `AuditEvent.resource_id` |
| `timestamp` | TIMESTAMPTZ | DEFAULT NOW() | `AuditEvent.timestamp` |
| `details` | JSONB | nullable | `AuditEvent.details` |

#### Table: `graph_nodes`

| Column | Type | Constraints | ORM model |
|--------|------|-------------|-----------|
| `id` | UUID | PK | `GraphNode.id` |
| `document_id` | UUID | FK → matter_documents | `GraphNode.document_id` |
| `name` | VARCHAR | NOT NULL | `GraphNode.name` |
| `type` | VARCHAR | NOT NULL | `GraphNode.type` |
| `description` | TEXT | nullable | `GraphNode.description` |

**Phase 5 DLG change:** `document_id` nullable; law nodes use `metadata.source`.

#### Table: `graph_edges`

| Column | Type | Constraints | ORM model |
|--------|------|-------------|-----------|
| `id` | UUID | PK | `GraphEdge.id` |
| `source_node_id` | UUID | FK → graph_nodes | `GraphEdge.source_node_id` |
| `target_node_id` | UUID | FK → graph_nodes | `GraphEdge.target_node_id` |
| `relationship` | VARCHAR | NOT NULL | `GraphEdge.relationship` |
| `chunk_index` | INT | NOT NULL | `GraphEdge.chunk_index` |

**DLG edge types (Phase 5):** `CONTAINS`, `REFERENCES`, `SUPERSEDES`

#### Planned Tables (Phase 1)

**`organizations`:**

| Column | Type | Description |
|--------|------|-------------|
| `id` | UUID PK | Organization ID |
| `name` | VARCHAR(255) | Display name |
| `created_at` | TIMESTAMPTZ | Creation time |

**`matter_members`:**

| Column | Type | Description |
|--------|------|-------------|
| `matter_id` | UUID FK | Composite PK part 1 |
| `user_id` | UUID FK | Composite PK part 2 |
| `role` | VARCHAR(20) | `viewer`, `editor`, `owner` |

#### Planned Tables (Phase 6)

**`chat_sessions`:**

| Column | Type | Description |
|--------|------|-------------|
| `id` | UUID PK | Session ID |
| `user_id` | UUID FK | Owner |
| `matter_id` | UUID FK nullable | Optional matter scope |
| `created_at` | TIMESTAMPTZ | Creation time |

**`chat_messages`:**

| Column | Type | Description |
|--------|------|-------------|
| `id` | UUID PK | Message ID |
| `session_id` | UUID FK | Parent session |
| `role` | VARCHAR | `user`, `assistant` |
| `content` | TEXT | Message body |
| `sources` | JSONB | Retrieved sources |
| `created_at` | TIMESTAMPTZ | Timestamp |

#### Planned Tables (Phase 8)

**`query_traces`:**

| Column | Type | Description |
|--------|------|-------------|
| `id` | UUID PK | Trace ID |
| `user_id` | UUID FK | Requester |
| `question` | TEXT | Original query |
| `pipeline_stages` | JSONB | Per-stage timing + hits |
| `created_at` | TIMESTAMPTZ | Timestamp |

#### Alembic Revision History

| Revision | File | Description |
|----------|------|-------------|
| `001_initial` | `001_initial_pgvector.py` | pgvector extension, document_chunks, users |
| `002_fix_users` | `002_fix_users_schema.py` | Users schema fix |
| `003_fix_chunks` | `003_fix_document_chunks.py` | Document chunks fix |
| `f75d11423144` | `f75d11423144_add_matters_and_documents.py` | matters, matter_documents, audit_events |
| `67cd5d0da8ec` | `67cd5d0da8ec_add_graph_tables.py` | graph_nodes, graph_edges |
| `004_rbac` | Planned | organizations, roles, matter_members |
| `005_hybrid` | Planned | content_tsv, GIN index, hybrid_search function |

#### Entity Relationship Diagram

```mermaid
erDiagram
    users ||--o{ matters : owns
    users ||--o{ audit_events : performs
    matters ||--o{ matter_documents : contains
    matter_documents ||--o{ document_chunks : "chunked into"
    matter_documents ||--o{ graph_nodes : "LLM extracted"
    graph_nodes ||--o{ graph_edges : source
    graph_nodes ||--o{ graph_edges : target
    users ||--o{ matter_members : "planned"
    matters ||--o{ matter_members : "planned"
    organizations ||--o{ users : "planned"
    users ||--o{ chat_sessions : "planned"
    chat_sessions ||--o{ chat_messages : "planned"
```

---

### 15.11 Configuration Reference (`config.py`)

**Source:** `v2/backend/src/config.py`  
**Loader:** `pydantic-settings` with `.env` file support  
**Instance:** `settings = Settings()`

#### Application Settings

| Key | Python attr | Env var | Default | Description |
|-----|-------------|---------|---------|-------------|
| App name | `app_name` | — | `JurisGuard V2` | FastAPI title |
| — | — | — | — | — |

#### Database & Cache

| Key | Python attr | Env var | Default | Description |
|-----|-------------|---------|---------|-------------|
| Database URL | `database_url` | `DATABASE_URL` | `postgresql+asyncpg://juris:juris_password@localhost:5433/juris_db` | Async SQLAlchemy DSN |
| Redis URL | `redis_url` | `REDIS_URL` | `redis://localhost:6380/0` | Celery broker + rate limiter |

#### LLM (Ollama)

| Key | Python attr | Env var | Default | Description |
|-----|-------------|---------|---------|-------------|
| Ollama base URL | `ollama_base_url` | `OLLAMA_BASE_URL` | `http://localhost:11434` | Host Ollama endpoint |
| Ollama model | `ollama_model` | `OLLAMA_MODEL` | `phi3.5` | Generation model name |
| Training mount | `training_mount_path` | `TRAINING_MOUNT_PATH` | `/training` | Fine-tune checkpoints + manifest |

#### Authentication

| Key | Python attr | Env var | Default | Description |
|-----|-------------|---------|---------|-------------|
| JWT secret | `auth_secret_key` | `AUTH_SECRET_KEY` | `change-me-in-production` | HS256 signing key |
| Token expiry | `auth_token_expire_minutes` | — | `60` | JWT TTL in minutes |

#### ML Models & Data Paths

| Key | Python attr | Env var | Default | Description |
|-----|-------------|---------|---------|-------------|
| Embedding dim | `embedding_dim` | — | `1024` | pgvector column size (bge-m3) |
| Embedding model path | `embedding_model_path` | `EMBEDDING_MODEL_PATH` | `/app/data/models/bge-m3` | Local bge-m3 weights |
| Reranker model path | `reranker_model_path` | `RERANKER_MODEL_PATH` | `/app/data/models/reranker` | cross-encoder weights |
| Law corpus path | `law_corpus_path` | `LAW_CORPUS_PATH` | `/app/data/raw/law_corpus` | GDPR/BGB source files |

#### RAG Pipeline

| Key | Python attr | Env var | Default | Description |
|-----|-------------|---------|---------|-------------|
| Retrieval top-K | `rag_top_k` | — | `20` | Vector search candidates |
| Rerank top-K | `rag_rerank_k` | — | `5` | Chunks sent to LLM |
| Max context chars | `rag_max_context_chars` | — | `6000` | Prompt context budget |

#### Planned Settings (Phase 2+)

| Key | Phase | Default | Description |
|-----|-------|---------|-------------|
| `hyde_enabled` | 2 | `False` | Global HyDE toggle |
| `rag_min_rerank_score` | 2 | `0.0` (tuned) | Confidence gate threshold |
| `graph_extract_enabled` | 5 | `False` | LLM graph extraction |
| `fts_config` | 2 | `german` | PostgreSQL text search config |
| `rrf_k` | 2 | `60` | Reciprocal Rank Fusion constant |

#### Environment File Example (`.env`)

```bash
# Database
DATABASE_URL=postgresql+asyncpg://juris:juris_password@db:5432/juris_db

# Redis
REDIS_URL=redis://cache:6379/0

# Ollama (host)
OLLAMA_BASE_URL=http://host.docker.internal:11434
OLLAMA_MODEL=phi3.5

# Auth — CHANGE IN PRODUCTION
AUTH_SECRET_KEY=your-256-bit-secret-here

# ML paths (container)
EMBEDDING_MODEL_PATH=/app/data/models/bge-m3
RERANKER_MODEL_PATH=/app/data/models/reranker
LAW_CORPUS_PATH=/app/data/raw/law_corpus

# Training (optional mount)
TRAINING_MOUNT_PATH=/training
```

#### Docker Compose Port Map

| Service | Host port | Container port | Purpose |
|---------|-----------|----------------|---------|
| api | 8002 | 8000 | FastAPI |
| db | 5433 | 5432 | PostgreSQL + pgvector |
| cache | 6380 | 6379 | Redis |
| worker | — | — | Celery (no exposed port) |
| Ollama | 11434 | — | Host process (not in compose) |

#### RAG Pipeline Config Flow

```mermaid
flowchart LR
    CFG["config.py Settings"]
    CFG --> EMB["embedding_model_path<br/>embedding_dim=1024"]
    CFG --> RR["reranker_model_path"]
    CFG --> RAG["rag_top_k=20<br/>rag_rerank_k=5<br/>rag_max_context_chars=6000"]
    CFG --> OLL["ollama_base_url<br/>ollama_model"]
    EMB --> VS["vector_store.search_similar"]
    RR --> RK["reranker.rerank"]
    RAG --> RP["rag.py answer_question"]
    OLL --> OC["ollama_client.generate"]
    VS --> RP
    RK --> RP
    RP --> OC
```

---

## Part 16 — Risk Register

Likelihood scale: **L** (Low), **M** (Medium), **H** (High)  
Impact scale: **L** (Low), **M** (Medium), **H** (High), **C** (Critical)

| ID | Risk | Category | Likelihood | Impact | Phase | Mitigation | Owner |
|----|------|----------|------------|--------|-------|------------|-------|
| R01 | **Cold RAG latency 3–7 min** on first request due to HF model download | ops | H | H | 0 | Pre-download `bge-m3` + reranker via `download_assets.py`; background warm on startup | Engineering |
| R02 | **Hallucinated legal citations** in answers erode DPO trust | RAG | M | C | 2 | Hybrid search + confidence gate + citation verifier; RAGAS faithfulness CI gate | Engineering |
| R03 | **Cross-matter data leak** via retrieval layer | security | M | C | 1 | RBAC at `search_similar()`; unit + E2E isolation tests | Engineering |
| R04 | **Prompt injection bypass** of keyword-only guard | security | M | H | 1 | Layer L2 regex + L3 BART Sentinel + L4 output sanitizer | Security |
| R05 | **LLM graph extraction produces 0 entities** — demo failure | graph | H | M | 5 | Cancel LLM graph; replace with deterministic DLG | Product |
| R06 | **RTX 4050 6GB VRAM OOM** if embed + LLM share GPU | ops | M | H | 0 | CPU-only embed/rerank in Docker; Ollama on host; `OLLAMA_MAX_LOADED_MODELS=1` | Engineering |
| R07 | **Celery worker not running** — uploads never process | ops | M | H | 0 | Worker in compose; E2E upload test; worker health in status | Engineering |
| R08 | **No frontend** — product unusable for target buyers | frontend | H | C | 4 | Phase 4 React SPA; Playwright smoke CI | Engineering |
| R09 | **Audit log write-only** — compliance procurement blocked | security | H | H | 1 | `GET /audit` + CSV export for `org_admin`+ | Engineering |
| R10 | **Marketing unverified accuracy claims** destroy legal-market credibility | rebrand | M | C | 3 | Phase 3 RAGAS baseline; deck uses only measured metrics | Product |
| R11 | **Colab GPU quota pause** delays fine-tune indefinitely | fine-tune | H | M | 7 | Continue on phi3.5; fine-tune is enhancement not blocker | Engineering |
| R12 | **94k training set quality issues** produce worse model than base | fine-tune | M | M | 7 | Eval comparison gate: ship only if faithfulness +3%; smoke test on 4050 first | ML |
| R13 | **V1/V2 split-brain** confuses developers and demos | rebrand | H | M | 9 | Archive V1 to `legacy/`; single compose at port 8002 | Engineering |
| R14 | **Orphan Ollama containers** cause port conflicts | ops | M | L | 0 | Document single Ollama policy; `docker compose --remove-orphans` | Ops |
| R15 | **German legal tokenization poor** in FTS (Art., §) | RAG | M | M | 2 | `pg_catalog.german` + custom dict; hybrid RRF compensates | Engineering |
| R16 | **Compare endpoint 2 sequential LLM calls** — slow UX | RAG | H | M | 2 | Parallel `asyncio.gather` with semaphore(1); query decomposition | Engineering |
| R17 | **Agent free-form ReAct** causes runaway LLM calls / cost | agent | M | H | 6 | Fixed-sequence planner; max 5 LLM calls; Redis job timeout | Engineering |
| R18 | **BDSG corpus gap** limits German DPO positioning | ops | M | M | 8 | Priority P0 ingest in Phase 8; ~200 chunks | Product |
| R19 | **JWT secret default `change-me-in-production`** in prod deploy | security | M | C | 1 | Enforce `AUTH_SECRET_KEY` in deploy checklist; fail startup if default | Security |
| R20 | **Worker runs as root** — container escape risk | security | M | M | 0 | Non-root `USER` in Dockerfile; uploads dir permissions | Security |
| R21 | **No rate limiting** — login brute force / chat abuse | security | M | M | 1 | Port V1 `slowapi`; Redis-backed limiter | Security |
| R22 | **pgvector HNSW index untuned** for laptop RAM | ops | M | M | 2 | Tune `m`, `ef_construction`; monitor query latency | Engineering |
| R23 | **HyDE adds 5–30s latency** per chat when enabled | RAG | M | M | 2 | Default off; per-request flag; serialize with chat queue | Engineering |
| R24 | **Air-gap install complexity** blocks regulated SME sales | ops | M | H | 8 | `airgap_bundle.sh`; offline runbook; USB demo kit | Ops |
| R25 | **OWASP LLM Top 10 gaps** fail enterprise security review | security | M | H | 8 | Checklist audit in Phase 8; pen test on injection + RBAC | Security |
| R26 | **Docker image size** slows air-gap transfer | ops | L | M | 0 | CPU torch only (fixed); target < 2 GB | Engineering |
| R27 | **Multi-tenant org isolation missing** — SaaS pivot blocked | security | M | M | 8 | `org_id` on matters, chunks, audit; optional RLS | Engineering |
| R28 | **Competitor leapfrog** (Harvey, Legora) while building | rebrand | M | M | 9 | Wedge on on-prem/air-gap; DPO niche; ship MVP at week 17 | Product |
| R29 | **WSL2 RAM limit (~7 GB)** causes OOM under load | ops | M | H | 0 | Solo Celery pool; single Ollama model; no GPU in api container | Engineering |
| R30 | **Law corpus staleness** (GDPR amendments, new BDSG) | ops | L | M | 8 | Versioned ingest; `metadata.effective_date`; re-ingest procedure | Legal/Ops |

### 16.1 Risk Heat Map

|  | Impact: L | Impact: M | Impact: H | Impact: C |
|--|-----------|-----------|-----------|-----------|
| **Likelihood: H** | R14 | R05, R16 | R01, R07 | R08 |
| **Likelihood: M** | R26 | R11, R12, R15, R18, R22, R23, R27, R28 | R04, R06, R09, R13, R17, R20, R21, R24, R25, R29 | R02, R03, R10, R19 |
| **Likelihood: L** | — | R30 | — | — |

### 16.2 Top 10 Risks by Severity Score

Severity = Likelihood (1–3) × Impact (1–4)

| Rank | ID | Risk | Score | Immediate action |
|------|-----|------|-------|------------------|
| 1 | R08 | No frontend | 12 | Start Phase 4 after Phase 3 |
| 2 | R02 | Hallucinated citations | 8 | Phase 2 hybrid + verifier |
| 3 | R03 | Cross-matter data leak | 8 | Phase 1 retrieval RBAC |
| 4 | R10 | Unverified marketing claims | 8 | Phase 3 baseline before GTM |
| 5 | R19 | Default JWT secret in prod | 8 | Deploy checklist now |
| 6 | R01 | Cold latency 3–7 min | 9 | Download models this week |
| 7 | R09 | Audit read API missing | 9 | Phase 1 priority |
| 8 | R06 | GPU OOM on 4050 | 6 | Maintain CPU-only Docker policy |
| 9 | R05 | LLM graph demo failure | 6 | Cancel; build DLG in Phase 5 |
| 10 | R25 | OWASP LLM gaps | 6 | Phase 8 security audit |

### 16.3 Risk Response Strategy by Phase

| Phase | Primary risks addressed | Strategy |
|-------|------------------------|----------|
| 0 | R01, R06, R07, R14, R20, R26, R29 | Stabilize infra; assets on disk; worker verified |
| 1 | R03, R04, R09, R19, R21 | Trust layer: RBAC, audit, rate limits, injection L2 |
| 2 | R02, R15, R16, R22, R23 | Retrieval quality: hybrid, verifier, confidence gate |
| 3 | R02, R10 | Measurable quality: RAGAS baseline gates marketing |
| 4 | R08 | Usability: React frontend for non-dev users |
| 5 | R05 | Graph credibility: DLG replaces LLM extraction |
| 6 | R17 | Controlled agent: fixed workflow, call limits |
| 7 | R11, R12 | Fine-tune optional: eval gate before swap |
| 8 | R18, R24, R25, R27, R30 | Enterprise: corpus, air-gap, security audit |
| 9 | R10, R13, R28 | GTM integrity: real metrics, single product, positioning |

---

## Part 17 — Glossary

### 17.1 Product & Domain Terms

| Term | Definition |
|------|------------|
| **JurisGuard** | On-premise legal intelligence platform; internal product name. V2 is the canonical codebase. |
| **BEWEIS** | V1 UI brand (German: "proof/evidence"). Retired in rebrand; archived to `legacy/v1/`. |
| **DPO** | Data Protection Officer — primary buyer persona for GDPR regulatory Q&A use case. |
| **Matter** | User-scoped legal workspace (deal room) containing uploaded documents and analysis history. |
| **Law corpus** | Indexed regulatory text (GDPR, BGB, planned BDSG) stored as `document_chunks` with `metadata.kind = "law"`. |
| **Air-gap** | Deployment mode with no outbound internet; all inference and embeddings run locally. |
| **On-prem** | Customer-hosted deployment (Docker on internal server) vs. SaaS cloud. |

### 17.2 RAG & Retrieval Terms

| Term | Definition |
|------|------------|
| **RAG** | Retrieval-Augmented Generation — retrieve relevant chunks, then condition LLM answer on them. |
| **pgvector** | PostgreSQL extension for vector similarity search; stores 1024-dim embeddings in `document_chunks`. |
| **bge-m3** | BAAI embedding model (`BAAI/bge-m3`); 1024 dimensions; runs on CPU in Docker. |
| **Cross-encoder reranker** | `cross-encoder/ms-marco-MiniLM-L-6-v2`; scores query-chunk pairs; top 20 → 5. |
| **RRF** | Reciprocal Rank Fusion — merges ranked lists from vector and BM25 branches: `score = Σ 1/(k + rank)`. |
| **HyDE** | Hypothetical Document Embeddings — LLM generates a hypothetical answer, embeds it, uses for retrieval. Implemented in `hyde.py`; not wired (Phase 2). |
| **BM25** | Best Matching 25 — classical lexical ranking; implemented via PostgreSQL full-text search (Phase 2). |
| **Hybrid search** | Combined vector (semantic) + BM25 (lexical) retrieval with RRF merge. |
| **Contextual retrieval** | Anthropic pattern: prepend document context to chunk before embedding at ingest time. |
| **Confidence gate** | Refusal layer when top rerank score falls below `rag_min_rerank_score`. |
| **Citation verifier** | Post-generation check that cited articles appear in retrieved source chunks. |
| **Parent-child chunks** | Hierarchical chunking: small child for retrieval, large parent for LLM context. |
| **Query decomposition** | Split complex question into sub-queries; retrieve for each; merge via RRF. |
| **HNSW** | Hierarchical Navigable Small World — approximate nearest neighbor index on pgvector embeddings. |

### 17.3 Graph Terms

| Term | Definition |
|------|------------|
| **Graph RAG** | Retrieval augmented by knowledge graph traversal (multi-hop reasoning). |
| **DLG** | Deterministic Legal Graph — rule-parsed GDPR/BGB structure graph; replaces LLM entity extraction. |
| **LLM graph extraction** | Current V2 approach: Ollama extracts entities/edges per chunk. **Cancelled** for contracts. |
| **Multi-hop query** | Question requiring traversal across related articles (e.g., "which article references Art. 6?"). |
| **CONTAINS** | DLG edge type: regulation → article → section hierarchy. |
| **REFERENCES** | DLG edge type: explicit citation link (e.g., chunk mentions "Art. 6(1)(f)"). |
| **SUPERSEDES** | DLG edge type: amendment replaces prior article (planned for BDSG). |

### 17.4 ML & Fine-Tuning Terms

| Term | Definition |
|------|------------|
| **Phi-3.5** | Microsoft small language model (`phi3.5` in Ollama); default inference model. |
| **jurisguard-v1** | Planned fine-tuned model name after Colab training → GGUF → `ollama create`. |
| **Ollama** | Local LLM runtime on host port 11434; serves quantized models. |
| **QLoRA** | Quantized Low-Rank Adaptation — memory-efficient fine-tuning via 4-bit base + LoRA adapters. |
| **LoRA** | Low-Rank Adaptation — train small adapter matrices instead of full model weights. |
| **GGUF** | Model file format for llama.cpp/Ollama inference. |
| **DPO** | Direct Preference Optimization — RLHF alternative (not currently in JurisGuard pipeline). |
| **Colab** | Google Colab — used for full 94k training on T4/A100 (not on RTX 4050). |
| **Smoke fine-tune** | `05_smoke_test_finetune.py` — 100 examples on 4050 to validate QLoRA pipeline only. |

### 17.5 Evaluation Terms

| Term | Definition |
|------|------------|
| **RAGAS** | Retrieval-Augmented Generation Assessment — framework for faithfulness, precision, recall, relevancy. |
| **Faithfulness** | RAGAS metric: is the answer grounded in retrieved context? |
| **Context precision** | RAGAS metric: are retrieved chunks relevant to the question? |
| **Context recall** | RAGAS metric: does retrieval cover the gold-standard information? |
| **Answer relevancy** | RAGAS metric: is the answer on-topic? |
| **Golden dataset** | Labeled eval set in `eval/golden/` with expected articles and chunk substrings. |
| **Logical eval** | Custom checks beyond RAGAS: citation existence, RBAC leak, refusal correctness. |
| **E2E functional test** | `scripts/e2e_functional_test.py` — 27 endpoint correctness tests (no perf thresholds). |
| **p95 latency** | 95th percentile response time; primary SLO metric for chat/analyze. |

### 17.6 Security & Compliance Terms

| Term | Definition |
|------|------------|
| **RBAC** | Role-Based Access Control — `member`, `matter_lead`, `org_admin`, `owner` (Phase 1). |
| **JWT** | JSON Web Token — Bearer auth issued on register/login; 60-min expiry. |
| **Sentinel** | V1 BART zero-shot classifier for prompt injection detection (Phase 1b port). |
| **Prompt injection** | Adversarial input attempting to override system instructions. |
| **Confidentiality level** | Document classification: `internal`, `restricted`, `privileged` (Phase 1). |
| **Audit trail** | `audit_events` table logging create/upload/analyze/compare/delete actions. |
| **OWASP LLM Top 10** | Security risk framework for LLM applications; checklist in Phase 8. |
| **GDPR** | EU General Data Protection Regulation — primary law corpus source (293 chunks). |
| **BGB** | German Civil Code (Bürgerliches Gesetzbuch) — 1,565 chunks indexed. |
| **BDSG** | German Federal Data Protection Act — planned Phase 8 corpus expansion. |

### 17.7 Infrastructure Terms

| Term | Definition |
|------|------------|
| **FastAPI** | Python async web framework; V2 API on port 8002. |
| **Celery** | Distributed task queue; `process_document_task` for async document ingest. |
| **Solo pool** | Celery worker pool with single process — prevents ML fork OOM. |
| **Alembic** | Database migration tool; revisions in `backend/alembic/versions/`. |
| **Docker Compose** | Multi-container orchestration: api, worker, db, cache. |
| **host.docker.internal** | Docker DNS for reaching host Ollama from containers. |
| **WSL2** | Windows Subsystem for Linux 2 — development environment. |
| **RTX 4050** | NVIDIA laptop GPU (6 GB VRAM) — hardware constraint for architecture decisions. |

### 17.8 Agent & Workflow Terms

| Term | Definition |
|------|------------|
| **Gap analysis** | Phase 6 agent workflow: extract obligations → search law → score alignment. |
| **Tool registry** | Internal functions (`search_law`, `search_document`, `get_article`, `cite_verify`) available to agent. |
| **ReAct** | Reasoning + Acting agent pattern — **not used** initially; fixed sequence preferred. |
| **Job queue** | Redis-backed async job with `job_id` polling for long-running agent tasks. |

### 17.9 Abbreviation Quick Reference

| Abbr | Expansion |
|------|-----------|
| API | Application Programming Interface |
| BM25 | Best Matching 25 |
| BDSG | Bundesdatenschutzgesetz |
| BGB | Bürgerliches Gesetzbuch |
| CI | Continuous Integration |
| CPU | Central Processing Unit |
| CSV | Comma-Separated Values |
| DLG | Deterministic Legal Graph |
| DMS | Document Management System |
| DPO | Data Protection Officer (role) / Direct Preference Optimization (ML) — context-dependent |
| E2E | End-to-End |
| EU | European Union |
| FTS | Full-Text Search |
| GIN | Generalized Inverted Index (PostgreSQL) |
| GGUF | GPT-Generated Unified Format |
| GTM | Go-To-Market |
| HF | Hugging Face |
| HNSW | Hierarchical Navigable Small World |
| HTTP | Hypertext Transfer Protocol |
| HyDE | Hypothetical Document Embeddings |
| JSONB | JSON Binary (PostgreSQL) |
| JWT | JSON Web Token |
| LLM | Large Language Model |
| LoRA | Low-Rank Adaptation |
| MVP | Minimum Viable Product |
| NDA | Non-Disclosure Agreement |
| OIDC | OpenID Connect |
| OOM | Out Of Memory |
| OWASP | Open Web Application Security Project |
| QLoRA | Quantized Low-Rank Adaptation |
| RAG | Retrieval-Augmented Generation |
| RAGAS | RAG Assessment |
| RBAC | Role-Based Access Control |
| Redis | Remote Dictionary Server |
| RRF | Reciprocal Rank Fusion |
| RLS | Row-Level Security |
| SAML | Security Assertion Markup Language |
| SLA / SLO | Service Level Agreement / Objective |
| SPA | Single Page Application |
| SSO | Single Sign-On |
| tsvector | PostgreSQL text search vector type |
| UUID | Universally Unique Identifier |
| VRAM | Video RAM |

---

## Part 18 — References & Changelog

### 18.1 Internal Repository References

| Document | Path | Description |
|----------|------|-------------|
| Phase Implementation Plan | `v2/docs/PHASE_IMPLEMENTATION_PLAN.md` | 34-week phased build plan (Phases 0–9) |
| Project Audit & Rebrand | `v2/docs/PROJECT_AUDIT_AND_REBRAND.md` | Honest market readiness assessment |
| Handoff Document | `v2/docs/HANDOFF.md` | Developer onboarding and architecture |
| Training Checkpoints | `v2/docs/TRAINING_CHECKPOINTS.md` | Colab resume and GGUF export guide |
| E2E Functional Test | `v2/scripts/e2e_functional_test.py` | 27/27 API correctness verification |
| Download Assets | `v2/scripts/download_assets.py` | Model and corpus download utility |
| Docker Compose | `v2/docker-compose.yml` | Runtime orchestration |
| Config | `v2/backend/src/config.py` | Application settings |
| Database Models | `v2/backend/src/db.py` | SQLAlchemy ORM tables |
| RAG Pipeline | `v2/backend/src/services/rag.py` | Core retrieval + generation |
| Fine-tune Notebook | `v2/notebooks/phi35_legal_finetune.ipynb` | Colab QLoRA training |

### 18.2 External References

| Source | URL | Relevance |
|--------|-----|-----------|
| Couchbase — Graph RAG vs Vector RAG | https://www.couchbase.com/blog/graph-rag-vs-vector-rag/ | Graph RAG positioning; when relationships matter |
| Meilisearch — Knowledge Graph vs Vector DB | https://www.meilisearch.com/blog/knowledge-graph-vs-vector-database-for-rag | Hybrid architecture rationale |
| Veriprajna — GraphRAG Architecture | https://veriprajna.com/services/graphrag-rag-architecture/ | HyDE, hybrid, multi-hop patterns |
| DEV — Hybrid Search with pgvector + RRF | https://dev.to/lpossamai/building-hybrid-search-for-rag-combining-pgvector-and-full-text-search-with-reciprocal-rank-fusion-6nk | Phase 2 hybrid search implementation |
| SitePoint — Local LLMs on 8GB | https://www.sitepoint.com/optimizing-local-llms-low-end-hardware-8gb/ | RTX 4050 / 6GB VRAM optimization |
| Anthropic — Contextual Retrieval | https://www.anthropic.com/news/contextual-retrieval | Contextual retrieval prepends pattern |
| RAGAS Documentation | https://docs.ragas.io/ | Evaluation framework for Phase 3 |
| OWASP LLM Top 10 | https://owasp.org/www-project-top-10-for-large-language-model-applications/ | Phase 8 security audit checklist |
| BAAI/bge-m3 | https://huggingface.co/BAAI/bge-m3 | Embedding model |
| ms-marco-MiniLM-L-6-v2 | https://huggingface.co/cross-encoder/ms-marco-MiniLM-L-6-v2 | Reranker model |
| Phi-3 Technical Report | https://arxiv.org/abs/2404.14219 | Base LLM architecture |
| Legora aOS | https://legora.com/product/aos | Agent OS competitive reference |
| Ollama Documentation | https://github.com/ollama/ollama/blob/main/docs/api.md | Local LLM API |
| pgvector | https://github.com/pgvector/pgvector | PostgreSQL vector extension |
| PostgreSQL German FTS | https://www.postgresql.org/docs/current/textsearch-dictionaries.html | German text search config |

### 18.3 Technology Stack Reference

| Layer | Technology | Version / Notes |
|-------|------------|-----------------|
| Language | Python | 3.12 |
| API framework | FastAPI | 0.3.0 app version |
| ORM | SQLAlchemy | 2.x async |
| Database | PostgreSQL + pgvector | Port 5433 |
| Cache/queue | Redis | Port 6380 |
| Task queue | Celery | Solo pool |
| LLM runtime | Ollama | phi3.5 default |
| Embeddings | sentence-transformers / bge-m3 | CPU, 1024-dim |
| Reranker | cross-encoder | CPU |
| Auth | PyJWT + bcrypt | HS256, 60-min TTL |
| Frontend (planned) | React 19 + Vite + TypeScript + Tailwind | Phase 4 |
| Container | Docker Compose | api, worker, db, cache |
| Migrations | Alembic | 5 revisions shipped |
| Eval (planned) | RAGAS + custom logical eval | Phase 3 |

### 18.4 Changelog

#### v1.0 — June 16, 2026

- Initial release of JurisGuard MASTER STRATEGY Parts 13–18.
- Part 13: Master feature checklist — 201 items across 10 categories with phase IDs and status.
- Part 14: Phase dependency graph and 34-week Gantt timeline with milestone gates.
- Part 15: API appendix — 20 shipped endpoints + 14 planned; full DB schema; config reference.
- Part 16: Risk register — 30 risks with likelihood, impact, mitigation, and phase mapping.
- Part 17: Glossary — 80+ terms covering RAG, graph, ML, security, and infrastructure.
- Part 18: References and changelog.

#### Pre-strategy implementation log (June 2026 session)

| Date | Change | Files | Impact |
|------|--------|-------|--------|
| 2026-06 | Celery worker service added to compose | `docker-compose.yml` | Document upload processes |
| 2026-06 | Shared uploads + hf_cache volumes | `docker-compose.yml` | Worker reads uploads |
| 2026-06 | `./data:/app/data` mount | `docker-compose.yml` | ML models visible in container |
| 2026-06 | Ollama host-gateway URL | `docker-compose.yml`, `.env` | LLM reachable |
| 2026-06 | CPU torch in Dockerfile | `Dockerfile` | Smaller image |
| 2026-06 | Injection guard → HTTP 400 | `chat.py`, `rag.py` | Correct semantics |
| 2026-06 | Compare dual RAG (doc + law) | `matters.py` | Compare uses contract |
| 2026-06 | Graph JSON parsing robustness | `graph_extractor.py` | Fewer empty graphs |
| 2026-06 | Celery solo pool | `docker-compose.yml` | Reliable ingest |
| 2026-06 | Non-blocking ML preload | `main.py` | Fast health response |
| 2026-06 | Skip empty model dirs | `embeddings.py`, `reranker.py` | HF fallback |
| 2026-06 | Worker asyncio fix | `worker.py` | Python 3.12 compat |
| 2026-06 | E2E functional test | `scripts/e2e_functional_test.py` | 27/27 pass |

#### Planned changelog entries (future)

| Version | Target | Expected contents |
|---------|--------|-------------------|
| v1.1 | Phase 1 complete | RBAC schema, audit API, rate limits documented |
| v1.2 | Phase 2 complete | Hybrid search, HyDE, citation verifier in API appendix |
| v1.3 | Phase 3 complete | RAGAS baseline numbers; updated risk register |
| v1.4 | Phase 4 complete | Frontend routes; Playwright CI |
| v2.0 | Phase 9 complete | Full MASTER STRATEGY consolidation; GTM metrics |

### 18.5 Document Maintenance Policy

| Rule | Description |
|------|-------------|
| **Update Part 13** | When any checklist item changes status (Done/Partial/Cancelled) |
| **Update Part 14** | When timeline slips > 1 week or phase order changes |
| **Update Part 15** | When endpoints, tables, or config keys are added/changed |
| **Update Part 16** | When new risks identified or mitigations verified |
| **Update Part 17** | When new acronyms introduced in codebase or docs |
| **Update Part 18** | On every strategy doc revision; append changelog entry |
| **Honesty policy** | Never mark eval/marketing items Done without measured evidence |
| **Review cadence** | Bi-weekly during active development; monthly post-Phase 9 |

### 18.6 Verification Commands (Appendix)

```bash
# Start stack
cd v2
docker start ollama 2>/dev/null || true
docker compose up -d
docker compose ps  # expect api, worker, db, cache Up

# Health
curl -s localhost:8002/health | jq .
curl -s localhost:8002/api/v1/status | jq .

# Download models (strongly recommended)
python scripts/download_assets.py --models --only bge-m3,reranker

# E2E verification
.venv/bin/python scripts/e2e_functional_test.py  # expect 27/27 PASS

# Corpus stats
curl -s localhost:8002/api/v1/corpus/stats | jq .

# OpenAPI path count
curl -s localhost:8002/openapi.json | jq '.paths | keys | length'
```

---

*End of JurisGuard MASTER STRATEGY — Parts 13–18. Generated June 2026 from `v2/` codebase state and PHASE_IMPLEMENTATION_PLAN.md.*


---




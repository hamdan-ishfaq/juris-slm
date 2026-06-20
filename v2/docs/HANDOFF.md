# JurisGuard V2 — Technical Handoff

Single engineering reference. Overview, architecture, and benchmarks: **[../README.md](../README.md)**.

---

## 1. What this is

JurisGuard V2 is an **on-prem legal intelligence platform**:

- **Research chat** over GDPR / BGB / BDSG / EU AI Act with citations  
- **Matter workspace** — upload contracts, analyze, compare to law  
- **Gap analysis** — bounded async workflow for DPO reports  
- **Enterprise** — org isolation, SSO/SCIM, legal hold, WORM audit chain  
- **Air-gap** — stack runs without outbound API calls when `LLM_PROVIDER=ollama`  

**Stack:** FastAPI · PostgreSQL/pgvector · Redis/Celery · React · Ollama or OpenRouter

---

## 2. Architecture decisions

| Decision | Rationale |
|----------|-----------|
| pgvector in Postgres | One DB for users, vectors, audit — air-gap friendly |
| Hybrid search (vector + BM25) | Legal queries use exact article numbers; keyword leg is essential |
| Model tiers T0–T3 | Retrieval always local; only T2 generation swaps cloud ↔ on-prem |
| Celery ingest | PDF/OCR/chunking takes minutes; API must not block |
| Bounded gap agent | Fixed tool chain (max 12 LLM calls) — predictable cost |
| Hash-chained audit | Tamper-evident log for DPO/regulator story |

---

## 3. RAG pipeline (implementation)

```
Query → guard/injection → cache? → embed (+HyDE T1) → hybrid retrieve
     → RRF → cross-encoder rerank (top 5) → DLG supplement (law only)
     → T2 generate → citation verify → T3 extractive fallback → audit
```

| Stage | File(s) |
|-------|---------|
| Orchestration | `backend/src/services/rag.py` |
| Hybrid + BM25 | `backend/src/services/vector_store.py` |
| Embeddings | `backend/src/services/embeddings.py` (bge-m3) |
| Rerank | `backend/src/services/reranker.py` |
| HyDE / expansion | `backend/src/services/hyde.py`, `query_enhance.py` |
| LLM routing | `backend/src/services/llm_client.py`, `ollama_client.py` |
| Citation verify | `backend/src/services/citation_verifier.py` |
| DLG (law edges) | `backend/src/services/dlg.py` |
| Ingest | `backend/src/ingest_law.py`, `backend/src/worker.py` |

---

## 4. Performance (June 2026, RTX 4050, fresh install)

**Report:** `eval/reports/ollama_eval_summary_latest.json`  
**Models:** T2 `mistral:7b-instruct-v0.3-q4_K_M` · T1 `qwen2.5:3b`

### Headline

| Metric | Dev (OpenRouter) | Air-gap (Mistral-7B) |
|--------|------------------|----------------------|
| Full logical pass | 97.3% (107/109) | **92.7% (101/110)** |
| End-to-end law hit | — | **88.6%** |
| 15-case context proxy | — | **93.3%** (not native RAGAS) |
| Contract hit rate | 100% (dev gate) | **85%** |
| Refusal correctness | — | **100%** |
| Forbidden violations | 0 | **0** |
| Offline gates | 20/20 | 20/20 |
| Unit tests | 100/100 | 100/100 |
| E2E functional | 49/49 | 49/49 |
| Law corpus chunks | — | **1,957** |

### Latency (Mistral air-gap)

| Endpoint | p50 | p90 | p95 |
|----------|-----|-----|-----|
| `/health` | 1.6 ms | 2.3 ms | 2.9 ms |
| `/corpus/stats` | 5.0 ms | 11.8 ms | 37.9 ms |
| `/chat` (full RAG) | **2.7 min** | **2.8 min** | **2.8 min** |

### Pipeline metrics (Mistral logical run)

| Metric | Value | Meaning |
|--------|-------|---------|
| `retrieval_source_hit_rate` | 70.5% | Gold phrases in **returned sources** (strict) |
| `answer_surface_hit_rate` | 86.4% | Gold in answer text |
| `end_to_end_hit_rate` | 88.6% | Gold in answer + sources |
| `retrieval_ok_generation_miss` | **0** | No cases where retrieval worked but generation failed |

**phi3.5 baseline (Jun 19):** 79.8% logical (87/109) — same retrieval stack, weaker T2.

---

## 5. Eval methodology (read before interviews)

- **Logical eval** checks gold **substrings** in answers/sources — regression harness, not formal logic.  
- **15-case “RAGAS”** in reports is an **in-house proxy** — label it `context_gold_recall_proxy`.  
- **Dev native-style baseline** faithfulness **0.87** in `eval/baseline.json` — cite this instead of proxy 1.0.  
- Re-run: `make eval-ollama-full` (~4h air-gap) or `make eval-logical` (dev, faster).

---

## 6. Interview talking points

**Strengths**

- Hybrid RRF + cross-encoder rerank — correct for legal exact-token + semantic mix  
- T3 extractive fallback + semantic grounding check (bge-m3 cosine)  
- Tiered T0–T3 design for data residency  
- 109/110-case eval harness separating retrieval vs generation metrics  

**Honest gaps**

- No formal entailment / rule engine  
- ms-marco reranker not legal-fine-tuned  
- Citation verify is label + cosine, not NLI  
- DLG is early curated edges, not full graph RAG  
- Air-gap latency ~3 min/chat on 6GB GPU  

**Sound bite**

> “We built a hybrid legal RAG pipeline with ~93% context proxy and 92.7% full-suite pass on Mistral-7B air-gap. The product is retrieve → rerank → augment → verify — not swapping in a smarter LLM alone.”

### CV bullets

- Built **hybrid legal RAG** (bge-m3 + BM25/RRF + cross-encoder + citation verify) — **92.7%** air-gap logical pass (110 cases), **93.3%** retrieval proxy.  
- On-prem matter workspace + enterprise audit on **FastAPI/pgvector/React**; **1,957-chunk** EU law corpus.  
- Eval harness separates **retrieval metrics** from **generation pass rate** (97.3% dev vs 92.7% air-gap).

---

## 7. Features

| Feature | Purpose |
|---------|---------|
| Grounded research chat | Law corpus Q&A with sources |
| Matters + upload | Per-deal document silo + RBAC |
| Analyze / compare | Scoped Q&A vs law baseline |
| Gap analysis | Async regulatory gap report |
| Contract editor | Version history, DOCX/PDF export |
| Clause library | Reusable standard clauses |
| Knowledge graph | Contract entities (supplements RAG) |
| Audit log | SHA-256 chain, CSV export, verify API |
| Legal hold | Block delete/export |
| SSO | SAML, OIDC, SCIM |
| White-label | `BRAND_*` env + `/api/v1/config/branding` |

---

## 8. Security

- JWT + refresh rotation  
- Roles: owner / member + matter viewer/editor  
- Confidentiality tiers: internal / restricted / privileged  
- Org isolation + optional Postgres RLS  
- Rate limits on chat; dev master for eval only  
- Templates: `docs/compliance/` (procurement — not SOC 2 certified)

---

## 9. API surface

| Group | Prefix |
|-------|--------|
| Auth | `/api/v1/auth` |
| Chat | `/api/v1/chat` |
| Matters | `/api/v1/matters` |
| Workflows | `/api/v1/workflows` |
| Audit | `/api/v1/audit` |
| Admin | `/api/v1/admin` |
| Config | `/api/v1/config` |
| Export | `/api/v1/export` |

OpenAPI: http://localhost:8002/docs

---

## 10. Known gaps / backlog

- Legal-domain reranker fine-tune  
- NLI-based citation verification  
- Custom fine-tuned legal GGUF (Colab QLoRA backlog)  
- Native RAGAS with judge LLM (`scripts/run_native_ragas.py` exists)  
- Word tracked-changes redline  
- Pen test not performed  

---

## 11. Key paths

| Path | Purpose |
|------|---------|
| `scripts/setup.sh` | Air-gap install wizard |
| `scripts/run_ollama_eval_complete.sh` | Full eval + summary |
| `scripts/warm_eval_fixtures.py` | Pre-ingest contract fixtures for eval |
| `eval/golden/*.jsonl` | Golden test cases |
| `eval/reports/ollama_eval_summary_latest.json` | Combined benchmark |
| `.env.example` / `.env.airgap.example` | Config templates |

---

*June 2026 · JurisGuard V2*

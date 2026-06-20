# JurisGuard V2

On-prem legal intelligence for EU privacy and in-house teams: grounded research chat over **GDPR, BGB, BDSG, and EU AI Act**, plus matter-scoped contract Q&A, gap analysis, and audit — with **no client data sent to public cloud LLMs** in air-gap mode.

> **Repo layout:** Active code lives in `v2/`. Legacy V1 at repo root was removed.

**Status:** Pilot-ready · June 2026  
**Hardware tested:** WSL2 · RTX 4050 6GB · CUDA bge-m3/rerank · Ollama Mistral-7B on host

| Service | URL |
|---------|-----|
| API | http://localhost:8002 |
| UI (dev) | http://localhost:5173 |
| OpenAPI | http://localhost:8002/docs |

---

## Architecture

```
┌─────────────────────────────────────────────────────────────┐
│  React UI — Research, Matters, Graph, Audit, Admin          │
└───────────────────────────┬─────────────────────────────────┘
                            │ REST + SSE
┌───────────────────────────▼─────────────────────────────────┐
│  FastAPI — auth, chat, matters, workflows, export, audit    │
├─────────────────────────────────────────────────────────────┤
│  RAG: hybrid search → rerank → LLM → citation verify        │
└───────┬───────────────────────────────┬─────────────────────┘
        │                               │
┌───────▼────────┐              ┌───────▼────────┐
│ Celery worker  │              │ PostgreSQL     │
│ ingest, OCR,   │              │ + pgvector     │
│ gap jobs       │              │ + audit chain  │
└───────┬────────┘              └────────────────┘
        │
┌───────▼────────┐     ┌─────────────────┐
│ Redis          │     │ Ollama /        │
└────────────────┘     │ OpenRouter LLM  │
                       └─────────────────┘
```

### Model tiers (T0–T3)

| Tier | Role | Component |
|------|------|-----------|
| **T0** | Retrieval (always local) | bge-m3 embeddings + BM25 + RRF + ms-marco cross-encoder rerank |
| **T1** | Aux (local Ollama) | HyDE, query decompose, graph extract — `qwen2.5:3b` |
| **T2** | Generation (swappable) | Air-gap: `mistral:7b-instruct-v0.3-q4_K_M` · Dev: OpenRouter phi-4-mini |
| **T3** | Safety fallback | Extractive answer from best chunk + bge-m3 cosine grounding check |

### Chat request flow

1. Auth + rate limit + prompt-injection guard  
2. Optional Redis query cache  
3. Embed query (+ optional HyDE / legal query expansion on T1)  
4. Hybrid retrieve (vector + keyword, RRF merge) → rerank top 5  
5. Optional DLG structural supplement (curated GDPR article edges)  
6. T2 grounded generation  
7. Citation verify (label in sources) + semantic context check → T3 fallback if needed  
8. Audit hash chain → response  

### Corpora

| Corpus | Content | Chunks (Jun 2026) |
|--------|---------|-------------------|
| **Law** | GDPR, BGB, BDSG, EU AI Act | **1,957** |
| **Matters** | Uploaded contracts per deal | Per org + confidentiality tier |

### What the pipeline does (and does not)

- **Does:** semantic (bge-m3) + lexical (BM25) retrieval, structural DLG supplement, soft LLM reasoning at generation  
- **Does not:** formal legal inference, entailment proving, or rule-based “IF Art. 6 THEN lawful” chains  
- **“Logical eval”** = automated substring/regression tests — not a reasoning capability  

---

## Performance

| Profile | Logical pass | Retrieval / quality | Chat p50 / p90 / p95 |
|---------|-------------|---------------------|----------------------|
| **Dev** (OpenRouter phi-4-mini) | **97.3%** (107/109) | 95.6% substring hit | ~13s / ~14s / ~14s |
| **Air-gap** (Mistral-7B + qwen2.5:3b) | **92.7%** (101/110) | 88.6% e2e · 93.3% proxy (15-case) · 85% contract | **~2.7 min** / **~2.8 min** / **~2.8 min** |
| **Air-gap baseline** (phi3.5) | 79.8% (87/109) | 95.6% substring hit | ~3.0 min p95 |

**Also:** 100/100 unit tests · 20/20 offline gates (RBAC + injection) · 49/49 E2E functional · 0 forbidden-content violations  

**Source:** `eval/reports/ollama_eval_summary_latest.json` (Mistral run, 2026-06-20)

**Interview line:** *“Product value is the hybrid RAG pipeline — retrieve, rerank, augment, verify — not raw LLM IQ. Mistral-7B air-gap hits 92.7% on the full 110-case suite vs 79.8% on phi3.5 with the same retrieval stack.”*

---

## Stack

FastAPI · PostgreSQL/pgvector · Redis · Celery · React · Ollama · bge-m3 · Docker · optional CUDA embed/rerank

---

## Quickstart

```bash
git clone https://github.com/hamdan-ishfaq/juris-slm.git
cd juris-slm/v2
cp .env.example .env          # set AUTH_SECRET_KEY (32+ chars)
make up-gpu && make migrate   # or: make up
python scripts/run_ingest_law.py --force
make ui-dev                   # http://localhost:5173
```

**Air-gap (no cloud LLM):**

```bash
ollama pull mistral:7b-instruct-v0.3-q4_K_M
ollama pull qwen2.5:3b
# .env: LLM_PROVIDER=ollama, copy from .env.airgap.example
bash scripts/setup.sh         # full wizard for IT handoff
make eval-ollama-full         # ~4h on RTX 4050 — writes summary JSON
```

**Dev login** (`DEV_MASTER_ENABLED=true`): `devmaster@example.com` / `DevMasterPass123!`

| Port | Service |
|------|---------|
| 8002 | API |
| 5433 | Postgres |
| 6380 | Redis |
| 11434 | Ollama (host) |
| 5173 | UI dev |

---

## Honest limitations

| Area | Limit |
|------|-------|
| Reasoning | Semantic + lexical retrieval + LLM soft reasoning — **no formal entailment engine** |
| Reranker | ms-marco MiniLM (web search training) — not legal-domain fine-tuned |
| Citation verify | Label presence in sources + bge-m3 cosine — not NLI/entailment |
| DLG | Small curated GDPR edge list — not full graph RAG over corpus |
| RAGAS label | 15-case **in-house proxy** only — do not claim “RAGAS 1.0”; dev baseline faithfulness **0.87** in `eval/baseline.json` |
| Latency | Air-gap chat ~3 min p95 on 6GB GPU — research UX, not instant chat |

---

## Problem & buyers

EU legal/privacy teams cannot use generic cloud AI on client work: **data residency** (NDA/DPIA), **hallucination risk** on citations, **siloed knowledge**, **no audit trail**.

| Buyer | Deliverable |
|-------|-------------|
| DPO | Grounded research + gap analysis report |
| In-house counsel | Matter upload, analyze, compare, export |
| CISO / IT | SSO/SCIM, org isolation, hash-chained audit |
| Regulated SME | Full air-gap: Ollama + local embeddings only |

---

## Eval & Makefile

```bash
make eval-offline          # 20/20 RBAC + injection (seconds)
make eval-logical          # 110-case suite + pipeline metrics
make eval-ollama-full      # offline + logical + ragas proxy + latency + summary
make test-unit             # 100 unit tests
make e2e                   # API functional
make brutal-gate           # fresh-stack regression
make airgap-bundle         # offline deploy tarball
```

White-label: `GET /api/v1/config/branding` + `BRAND_*` env vars.

---

## Project layout

```
v2/
├── backend/src/       # FastAPI, RAG, workers, migrations
├── frontend/src/      # React SPA
├── eval/              # Golden sets + reports
├── docs/HANDOFF.md    # API, security, interview deep-dive
├── scripts/           # ingest, eval, setup.sh
└── Makefile
```

---

## Documentation

**[docs/HANDOFF.md](docs/HANDOFF.md)** — API surface, security, CV bullets, known gaps, file map.

https://github.com/hamdan-ishfaq/juris-slm

*JurisGuard V2 · June 2026*

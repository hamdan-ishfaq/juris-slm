# JurisGuard V2 — Operations Runbook

**Phase:** 0 (stabilization)  
**API:** http://localhost:8002  
**Last updated:** June 2026

---

## 1. Prerequisites

| Component | Check |
|-----------|--------|
| Docker + Compose v2 | `docker compose version` |
| Ollama on host | `curl -s localhost:11434/api/tags` |
| Phi-3.5 model | `ollama pull phi3.5` |
| Python venv (host scripts) | `cd v2 && python3 -m venv .venv && source .venv/bin/activate` |

---

## 2. One-command start

```bash
cd v2
cp -n .env.example .env
make up          # docker compose up -d --build
make migrate     # alembic upgrade head
make models      # download bge-m3 + reranker if missing
make e2e         # 29 functional tests (Phase 0)
```

---

## 3. Cold start (first time)

```bash
cd v2
python3 -m venv .venv && source .venv/bin/activate
pip install -r scripts/requirements-download.txt

# Law texts + ML models (required before demos)
python scripts/download_assets.py --datasets --only gdpr,bgb
python scripts/download_assets.py --models --only bge-m3,reranker
python scripts/verify_assets.py --models-only

# Ollama (host, not in compose)
ollama pull phi3.5

docker compose up -d --build
docker compose exec api alembic upgrade head

# Ingest law corpus if empty
docker compose exec api python /app/src/ingest_law.py
# Or from host: python scripts/run_ingest_law.py

python scripts/e2e_functional_test.py
```

---

## 4. Warm start (daily dev)

```bash
docker start ollama    # if Ollama runs in Docker on host
cd v2 && docker compose up -d
curl -s localhost:8002/health
python scripts/e2e_functional_test.py
```

---

## 5. Services and ports

| Service | Host port | Notes |
|---------|-----------|--------|
| API | 8002 | FastAPI |
| Postgres | 5433 | pgvector |
| Redis | 6380 | Celery broker |
| Ollama | 11434 | **Host only** — `host.docker.internal` in `.env` |

### Orphan containers

If you previously ran an Ollama service inside compose:

```bash
docker compose up -d --remove-orphans
```

Use **one** Ollama instance on the host — do not run `v2-ollama-1` alongside it.

---

## 6. Migrations (Bug 0.2.2)

Alembic is mounted from `./backend/alembic` — host and container share revisions.

```bash
docker compose exec api alembic upgrade head
docker compose exec api alembic current
```

Fresh DB reset (destructive):

```bash
docker compose down -v
docker compose up -d db cache
docker compose exec api alembic upgrade head
```

---

## 7. Model assets (Bug 0.2.1)

Paths inside container: `/app/data/models/bge-m3`, `/app/data/models/reranker`  
Host: `v2/data/models/`

```bash
python scripts/verify_assets.py --models-only
python scripts/download_assets.py --models --only bge-m3,reranker
```

`GET /api/v1/status` reports `models.embedding_ready`, `models.reranker_ready`, `models.ready`.

**Symptom:** First chat downloads ~2GB from HuggingFace → run `make models` before demos.

---

## 8. Worker and Celery (Bugs 0.2.5, 0.2.7)

Worker runs as non-root user `juris` (uid 1000). Uploads volume: `uploads_data` → `/app/src/data/uploads`.

Check worker health:

```bash
curl -s localhost:8002/api/v1/status | python3 -m json.tool
# Expect: "celery": { "reachable": true, "workers": ["celery@..."] }
docker compose logs worker --tail 50
```

If upload fails with permission denied:

```bash
docker compose run --user root --rm worker chown -R juris:juris /app/src/data/uploads
docker compose restart worker
```

---

## 9. Compare endpoint (Bug 0.2.6 — waived Phase 0)

`POST /matters/{id}/compare` runs **two sequential LLM calls** (document RAG + law RAG). Slow but correct. Parallelization deferred to Phase 2.

---

## 10. E2E testing

**Canonical suite:** `scripts/e2e_functional_test.py` (functional correctness, no perf gates)

```bash
python scripts/e2e_functional_test.py
# Expect: 0 failed (Phase 0 adds celery + models-on-disk checks)
```

**Deprecated:** `backend/tests/test_e2e_comprehensive.py` — wrong perf thresholds; do not use in CI.

### CI without Ollama

Set `CI_SKIP_LLM=1` to skip chat/compare tests on runners without GPU/Ollama (partial pass). Full gate requires Ollama on self-hosted runner.

---

## 11. Troubleshooting

| Symptom | Fix |
|---------|-----|
| 503 on chat | Ollama down → `ollama serve` / `docker start ollama` |
| Chat timeout | Models downloading → `make models`; wait for preload |
| Document stuck processing | Worker down → `docker compose ps worker`; check logs |
| `celery.reachable: false` | Redis down or worker crashed → `docker compose restart worker cache` |
| Injection test expects 400 | Working as designed |
| Port 8002 in use | Stop V1 stack or change compose port |

---

## 12. Phase 0 exit checklist

- [ ] `python scripts/verify_assets.py --models-only` → exit 0
- [ ] `docker compose ps` → api, worker, db, cache Up
- [ ] `/api/v1/status` → `celery.reachable: true`, `models.ready: true`
- [ ] `python scripts/e2e_functional_test.py` → 0 failed
- [ ] `docs/RUNBOOK.md` (this file) reviewed

---

*Next phase: Phase 1 RBAC — see JurisGuard_MASTER_STRATEGY.md Part 7.*

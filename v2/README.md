# JurisGuard V2

**On-premise legal intelligence for EU teams** — grounded research chat, matter-scoped contract analysis, enterprise SSO, legal hold, and tamper-evident audit. Client data stays in your VPC; no public cloud LLM required.

**Status:** Phases 1–10 complete · Pilot-ready · June 2026

| | |
|---|---|
| **API** | http://localhost:8002 |
| **UI (dev)** | http://localhost:5173 |
| **Docs** | http://localhost:8002/docs |

---

## What it does

- **Research chat** — GDPR, BGB, BDSG, EU AI Act with citations (hybrid RAG + rerank)
- **Matter workspace** — upload NDAs/DPAs, analyze, compare against law corpus
- **Gap analysis** — bounded DPO workflow (async job, structured report)
- **Contract editor** — in-browser edit, version history, PDF/DOCX export
- **Enterprise** — org isolation, SAML/OIDC/SCIM, legal hold, SHA-256 audit chain
- **Air-gap** — `LLM_PROVIDER=ollama`, offline bundle, no external API calls

---

## Quick start

```bash
cd v2
cp .env.example .env          # set AUTH_SECRET_KEY; optional OPENROUTER_API_KEY for dev
make up && make migrate       # Docker: API, Postgres, Redis, worker
make ui-dev                   # React UI → http://localhost:5173
```

**Dev login** (local only, when `DEV_MASTER_ENABLED=true`):

- Email: `devmaster@example.com`
- Password: `DevMasterPass123!`

**GPU stack** (CUDA embeddings + rerank, host Ollama):

```bash
make up-gpu
bash scripts/setup_ollama_gpu.sh   # pull phi3.5 on host GPU
make verify-gpu
```

---

## Profiles

Flip via `.env` — no code changes. See [ARCHITECTURE.md](ARCHITECTURE.md).

| Profile | `LLM_PROVIDER` | Generation | External calls |
|---------|----------------|------------|----------------|
| **dev** | `openrouter` | phi-4-mini | OpenRouter only |
| **air-gap** | `ollama` | phi3.5 | **None** |

Model tiers: **T0** embeddings/rerank (always local) → **T1** aux HyDE/graph → **T2** answer LLM → **T3** extractive fallback.

---

## Common commands

```bash
make test-unit              # 100+ unit tests
make test-integration       # org isolation, SSO, WORM audit, etc.
make e2e                    # 43 API functional tests
make ui-e2e                 # Playwright UI smoke

make eval-logical           # 109 golden API cases
make eval-ollama-full       # full Ollama suite + summary JSON
make brutal-gate            # combined CI gate

make ui-dev                 # start Vite (detects port 5173 in use)
make ui-dev-restart         # kill stale Vite + restart
make ui-dev-stop            # stop dev server
make ui-build               # production bundle

make airgap-bundle          # offline deploy tarball
```

---

## Services & ports

| Service | Port | Notes |
|---------|------|-------|
| API | **8002** | FastAPI |
| UI (Vite) | **5173** | proxies `/api` → 8002 |
| Postgres | **5433** | pgvector |
| Redis | **6380** | Celery |
| Ollama | **11434** | host or Docker profile |

All application code is in this repository under `v2/`.

---

## Measured quality (June 2026)

| Suite | Dev (OpenRouter) | Air-gap (Ollama phi3.5, CUDA) |
|-------|------------------|-------------------------------|
| Logical offline | 20/20 | 20/20 |
| Logical API | 107/109 (99.1%) | 87/109 (79.8%) |
| RAGAS proxy (15 cases) | faithfulness 0.87 | 15/15 complete, proxy 1.0 |
| Chat latency p95 | ~17s | ~3 min |

Reports: `eval/reports/ollama_eval_summary_latest.json`

---

## Documentation

| Doc | Use when |
|-----|----------|
| **[docs/COMPLETE_PROJECT_HANDOFF.md](docs/COMPLETE_PROJECT_HANDOFF.md)** | Onboarding, interviews, CV — full explanation |
| **[docs/PROJECT_MASTER_HANDOFF.md](docs/PROJECT_MASTER_HANDOFF.md)** | Business / investor / procurement |
| **[ARCHITECTURE.md](ARCHITECTURE.md)** | Model tiers, RAG pipeline, profile flip |
| **[docs/PHASE_9_ENTERPRISE_PLAN.md](docs/PHASE_9_ENTERPRISE_PLAN.md)** | Enterprise feature spec |
| **[docs/README-INSTALL.md](docs/README-INSTALL.md)** | Detailed install & air-gap |
| **[SECURITY.md](SECURITY.md)** | Hardening & pen-test scope |
| **[docs/compliance/CONTROL_MATRIX.md](docs/compliance/CONTROL_MATRIX.md)** | SOC 2 / ISO mapping |

---

## Repository layout

```
v2/
├── backend/src/       # FastAPI — routers, services, worker
├── frontend/src/      # React SPA
├── eval/              # Golden tests + reports
├── docs/              # Handoff, compliance, SSO
├── scripts/           # ingest, eval, setup, airgap bundle
├── docker-compose.yml
├── docker-compose.gpu.yml
└── Makefile
```

---

## Troubleshooting

**Port 5173 already in use**

```bash
make ui-dev          # prints URL if already running
make ui-dev-restart  # fresh start
```

**UI CSS / Vite errors** — ensure latest `styles.css`; restart with `make ui-dev-restart`.

**WSL + Windows browser** — use the WSL IP printed by `make ui-dev` if `localhost:5173` fails.

**Ollama segfault on WSL** — use HTTP API (`curl localhost:11434`) or Docker profile; CLI may crash but API works.

**Push / auth** — see root README for GitHub remote setup.

---

## License

See repository license. For questions: [hamdan-ishfaq/juris-slm](https://github.com/hamdan-ishfaq/juris-slm).

*JurisGuard V2 · June 2026*

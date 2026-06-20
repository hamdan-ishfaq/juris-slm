# JurisGuard

Legal AI platform with on-prem RAG, matter workspaces, and enterprise controls.

> **Active development is in [`v2/`](v2/)** — use that directory for install, run, and docs.  
> Legacy V1 (`backend/`, `frontend/` at repo root) is frozen; do not mix ports or databases.

---

## JurisGuard V2 at a glance

| | |
|---|---|
| **What** | Self-hosted legal copilot — GDPR/BGB research, contract analyze/compare, DPO gap reports |
| **Stack** | FastAPI · PostgreSQL/pgvector · Redis/Celery · React · Ollama or OpenRouter |
| **Status** | Phases 1–10 shipped · pilot-ready · June 2026 |

```bash
git clone https://github.com/hamdan-ishfaq/juris-slm.git
cd juris-slm/v2
cp .env.example .env
make up && make migrate
make ui-dev    # http://localhost:5173
```

Full guide: **[v2/README.md](v2/README.md)**

Handoff / interview doc: **[v2/docs/COMPLETE_PROJECT_HANDOFF.md](v2/docs/COMPLETE_PROJECT_HANDOFF.md)**

---

## Documentation index

| Document | Path |
|----------|------|
| **Quick start & commands** | [v2/README.md](v2/README.md) |
| **Complete handoff (interviews, CV)** | [v2/docs/COMPLETE_PROJECT_HANDOFF.md](v2/docs/COMPLETE_PROJECT_HANDOFF.md) |
| **Business / investor summary** | [v2/docs/PROJECT_MASTER_HANDOFF.md](v2/docs/PROJECT_MASTER_HANDOFF.md) |
| **Architecture** | [v2/ARCHITECTURE.md](v2/ARCHITECTURE.md) |
| **Install & air-gap** | [v2/docs/README-INSTALL.md](v2/docs/README-INSTALL.md) |

---

## GitHub

**Repository:** [github.com/hamdan-ishfaq/juris-slm](https://github.com/hamdan-ishfaq/juris-slm)  
**Default branch:** `master` (V2 work)

---

*Last updated: June 2026*

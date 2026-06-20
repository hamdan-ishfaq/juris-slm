# JurisGuard

On-prem legal intelligence platform — grounded RAG over GDPR/BGB and matter documents, with enterprise SSO, legal hold, and tamper-evident audit.

**All application code lives in [`v2/`](v2/).**

---

## Quick start

```bash
git clone https://github.com/hamdan-ishfaq/juris-slm.git
cd juris-slm/v2
cp .env.example .env          # set AUTH_SECRET_KEY
make up && make migrate
make ui-dev                   # http://localhost:5173
```

| Service | URL |
|---------|-----|
| API | http://localhost:8002 |
| UI (dev) | http://localhost:5173 |
| API docs | http://localhost:8002/docs |

**Local dev login** (`DEV_MASTER_ENABLED=true`): `devmaster@example.com` / `DevMasterPass123!`

---

## Documentation

| Doc | Purpose |
|-----|---------|
| [v2/README.md](v2/README.md) | Commands, profiles, ports, troubleshooting |
| [v2/docs/COMPLETE_PROJECT_HANDOFF.md](v2/docs/COMPLETE_PROJECT_HANDOFF.md) | Full architecture guide (interviews, onboarding) |
| [v2/docs/PROJECT_MASTER_HANDOFF.md](v2/docs/PROJECT_MASTER_HANDOFF.md) | Business / investor summary |
| [v2/ARCHITECTURE.md](v2/ARCHITECTURE.md) | Model tiers & RAG pipeline |

---

## Repository layout

```
juris-slm/
├── v2/                 # ← entire product (backend, frontend, eval, docs)
│   ├── backend/
│   ├── frontend/
│   ├── eval/
│   ├── docs/
│   ├── scripts/
│   └── Makefile
├── .github/workflows/  # CI for v2
└── README.md           # this file
```

---

## GitHub

https://github.com/hamdan-ishfaq/juris-slm

*June 2026*

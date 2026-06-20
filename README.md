# JurisGuard

Self-hosted legal AI for EU teams — hybrid RAG over GDPR/BGB/BDSG/EU AI Act and client contracts, with audit trail and air-gap deployment.

> **All active development is in [`v2/`](v2/).** Legacy V1 was removed.

| Doc | Purpose |
|-----|---------|
| **[v2/README.md](v2/README.md)** | Architecture, benchmarks, quickstart, limitations |
| **[v2/docs/HANDOFF.md](v2/docs/HANDOFF.md)** | API, security, interview guide, file map |

```bash
git clone https://github.com/hamdan-ishfaq/juris-slm.git
cd juris-slm/v2 && cp .env.example .env && make up && make migrate && make ui-dev
```

**Air-gap headline (Jun 2026):** Mistral-7B · **92.7%** logical pass (101/110) · **~2.8 min** chat p95 · 1,957 law chunks

https://github.com/hamdan-ishfaq/juris-slm

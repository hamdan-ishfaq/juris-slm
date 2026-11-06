# Security — JurisGuard V2

## Reporting vulnerabilities

Report security issues to your `{CUSTOMER}` security contact or internal engineering lead. Do not disclose publicly before coordinated fix.

---

## Architecture summary

- **API:** FastAPI (Python), JWT bearer auth  
- **Data:** PostgreSQL + pgvector, Redis, local file uploads  
- **Workers:** Celery async ingest / gap analysis  
- **Frontend:** React SPA served from API or separate static host  

---

## Authentication boundaries (pen test scope)

| Endpoint pattern | Auth | Notes |
|------------------|------|-------|
| `/api/v1/auth/*` | Public (login/register) | Rate-limited |
| `/api/v1/auth/saml/*`, `/oidc/*` | Public callbacks | Signature verify on SAML |
| `/api/v1/scim/*` | SCIM bearer token | Org-scoped |
| `/api/v1/matters/*` | JWT + matter RBAC | Org isolation |
| `/api/v1/audit/*` | JWT `org_admin+` | Hash chain on events |
| `/api/v1/admin/*` | JWT `org_admin+` | |
| `/health` | Public | No sensitive data |

Cross-org access must return **404** (not 403) for existence hiding — verified in E2E.

---

## Hardening checklist (production)

- [ ] Set strong `AUTH_SECRET_KEY`  
- [ ] Disable `REGISTRATION_OPEN` when using SCIM-only provisioning  
- [ ] Enable TLS at reverse proxy  
- [ ] Restrict `ALLOWED_ORIGINS`  
- [ ] Enable `RLS_ENABLED=true` for Postgres defense-in-depth  
- [ ] Run `GET /api/v1/audit/verify` after upgrades  
- [ ] Optional: `WORM_BACKEND=filesystem` for sealed bundles  

---

## Sub-processors (optional cloud LLM)

When `LLM_PROVIDER=openrouter`, prompts may transit OpenRouter. Air-gap profile uses local Ollama only — see `.env.airgap` template.

---

## Compliance documentation

- Control matrix: `docs/compliance/CONTROL_MATRIX.md`  
- DR template: `docs/DISASTER_RECOVERY.md`  
- GDPR erasure: `docs/GDPR_ERASURE.md`  
- SSO setup: `docs/SSO_SETUP.md`  

---

## Evidence bundle

```bash
./scripts/compliance_evidence.sh
```

Produces `dist/compliance_evidence_*.zip` with redacted config snapshot and test summary.

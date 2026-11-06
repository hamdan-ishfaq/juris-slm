# JurisGuard V2 — Control Matrix (SOC 2 / ISO 27001 / GDPR)

**Version:** 1.0 (Phase 9G)  
**Scope:** On-prem / air-gap deployment of JurisGuard V2  
**Status:** Readiness mapping — not a certification statement

This matrix maps common enterprise controls to **implemented product evidence** in Phases 1–9. Use it for procurement questionnaires and internal audit dry-runs.

---

## SOC 2 Trust Services Criteria

| Control | Requirement | JurisGuard evidence | Phase | Test / artifact |
|---------|-------------|---------------------|-------|-----------------|
| **CC6.1** | Logical access | JWT auth, role hierarchy (`member` → `owner`), matter-level RBAC | 1, 4 | `test_rbac*.py`, Help RBAC matrix |
| **CC6.2** | Registration / provisioning | Local registration + SCIM 2.0 user provision/deprovision | 9C | `test_scim_sso.py` |
| **CC6.3** | SSO / federation | OIDC + SAML SP, group→role mapping | 9C | `test_saml_sp.py`, `docs/SSO_SETUP.md` |
| **CC6.6** | Boundary protection | Org isolation on matters, chunks, audit; optional Postgres RLS | 9A | `test_org_isolation*.py`, `test_org_rls.py` |
| **CC6.7** | Transmission | TLS at reverse proxy (customer-operated); CORS allowlist | 8 | `config.py` `ALLOWED_ORIGINS` |
| **CC7.1** | Detection / monitoring | Append-only audit log, CSV export, hash chain verify | 1, 9E | `GET /api/v1/audit/verify`, `test_audit_worm_integration.py` |
| **CC7.2** | Incident response | Runbook template | 9G | `docs/compliance/INCIDENT_RESPONSE.md` |
| **CC7.3** | Eval / quality gates | RAGAS/logical eval, CI test suites | 5, 8 | `make eval-logical`, `make test-integration` |
| **CC8.1** | Change management | Git + PR workflow (customer process); Alembic migrations | 8 | `backend/alembic/versions/` |

---

## ISO 27001 Annex A (selected)

| Control | Title | JurisGuard evidence | Phase |
|---------|-------|---------------------|-------|
| **A.5.15** | Access control | RBAC + matter roles + confidentiality tiers | 1, 4 |
| **A.5.16** | Identity management | Users, orgs, SCIM, SSO | 9A, 9C |
| **A.5.28** | Collection of evidence | Audit events, WORM hash chain, daily seal API | 9E |
| **A.5.33** | Protection of records | Legal hold blocks delete/erasure; audit immutability | 9B, 9E |
| **A.8.2** | Privileged access | `org_admin` / `owner` for admin, audit, holds | 4 |
| **A.8.9** | Configuration management | `.env` profile, air-gap bundle | 8 |
| **A.8.15** | Logging | Chat query hash, document actions, agent steps | 1, 9D |
| **A.8.24** | Cryptography | bcrypt passwords, SHA-256 audit chain | 9E |

---

## GDPR (product-relevant articles)

| Article | Topic | JurisGuard capability | Phase |
|---------|-------|----------------------|-------|
| **Art. 17** | Right to erasure | Chunk deletion worker; legal-hold gate; erasure certificate audit event | 9B, 9E |
| **Art. 28** | Processor terms | Customer-operated deployment; optional OpenRouter disclosure in vendor list | 9G |
| **Art. 30** | Records of processing | ROPA template (customer-owned) | 9G |
| **Art. 32** | Security of processing | Org isolation, RBAC, audit, SSO | 9A–9C |
| **Art. 35** | DPIA support | Grounded RAG citations, gap analysis report export | 9D |

---

## Feature → control quick reference

| Feature | Controls supported |
|---------|-------------------|
| Multi-tenant org isolation (9A) | CC6.6, A.5.16 |
| Legal hold (9B) | CC6.6, A.5.33, GDPR Art. 17 |
| SAML/OIDC/SCIM (9C) | CC6.2, CC6.3 |
| Bounded gap analysis agent (9D) | CC7.3, GDPR Art. 35 |
| WORM audit chain (9E) | CC7.1, A.5.28 |
| Contract workspace + versioning (9F) | CC7.1, A.8.15 |
| Eval gates + CI | CC7.3, CC8.1 |

---

## Coverage summary

| Area | Mapped controls | Notes |
|------|-----------------|-------|
| Access & identity | 12 | SSO optional profile |
| Logging & audit | 8 | Hash chain + seal API |
| Data lifecycle | 6 | Hold + erasure paths |
| Operations | 5 | DR/BCP customer-run |
| **Overall** | **~85%** of pilot control set | Remaining: formal pen test, org policies signed |

---

## Gaps / customer responsibilities

1. **Physical security** — customer data center / VPC  
2. **TLS certificates** — customer reverse proxy  
3. **Backup & restore** — customer Postgres/filesystem (see `docs/DISASTER_RECOVERY.md`)  
4. **Signed policies** — Information Security Policy, retention policy (templates in `docs/compliance/`)  
5. **External penetration test** — use `SECURITY.md` API boundary section for scoping  

---

## Evidence collection

Run `./scripts/compliance_evidence.sh` to produce a redacted evidence bundle (test summary, audit verify sample, config snapshot).

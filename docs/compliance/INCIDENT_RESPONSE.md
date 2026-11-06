# Incident Response Plan (Template)

**Owner:** DevOps / Security lead · **Classification:** Internal

---

## Severity levels

| Level | Example | Response time |
|-------|---------|---------------|
| S1 | Confirmed cross-org data leak | 1 hour |
| S2 | Auth bypass, audit chain failure | 4 hours |
| S3 | Service outage, failed backup | 8 hours |
| S4 | Low-risk vulnerability | Next sprint |

---

## S1 — Data breach playbook

1. **Contain** — disable affected accounts; `docker compose stop api` if active exfil  
2. **Assess** — run `GET /api/v1/audit/verify`; review `audit_events` for anomalous access  
3. **Notify** — DPO within 72h (GDPR Art. 33/34 assessment)  
4. **Remediate** — patch, rotate `AUTH_SECRET_KEY`, force re-auth  
5. **Post-incident** — update control matrix; add regression test  

---

## Detection sources

- Audit verify failures  
- Integration test failures in CI  
- Customer report / pen test finding  
- Abnormal `agent_step` volume (9D budget exceeded attempts)

---

## Contacts

| Role | Name | Contact |
|------|------|---------|
| Incident commander | TBD | |
| DPO | TBD | |
| Engineering lead | TBD | |

---

## Evidence preservation

Do **not** truncate `audit_events` during investigation. Export CSV + verify chain before remediation.

See also: `docs/DISASTER_RECOVERY.md`

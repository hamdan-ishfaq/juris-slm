# Disaster Recovery — On-Prem Template (Phase 9G)

**Audience:** Customer DevOps / DPO operating JurisGuard V2 on-premises  
**RTO target (pilot):** 4 hours · **RPO target (pilot):** 24 hours  

Customize placeholders `{CUSTOMER}`, `{SITE}`, `{CONTACT}` before production use.

---

## 1. System components

| Component | Data | Backup priority |
|-----------|------|-----------------|
| PostgreSQL (`juris_db`) | Matters, chunks, vectors, audit, users | **Critical** |
| Redis | Celery queue, workflow job status | Medium (ephemeral OK) |
| Upload volume (`backend/data/uploads`) | Original contract files | **Critical** |
| Law corpus (`data/raw/law_corpus`) | Statutory reference corpus | High (re-ingest possible) |
| Embedding models | Local model cache | Low (re-download) |

---

## 2. Backup procedures

### 2.1 PostgreSQL

```bash
# Daily logical backup (example)
pg_dump -h localhost -p 5433 -U juris juris_db | gzip > /backup/juris/juris_db_$(date +%F).sql.gz
```

Retain 30 daily + 12 monthly copies per retention policy.

### 2.2 File uploads

```bash
rsync -a /path/to/v2/backend/src/data/uploads/ /backup/juris/uploads/
```

### 2.3 Audit integrity

After restore, run:

```bash
curl -H "Authorization: Bearer $ADMIN_TOKEN" \
  "http://localhost:8002/api/v1/audit/verify"
```

Expect `"valid": true`. Investigate any `row_hash_mismatch`.

---

## 3. Restore procedures

1. Stop API and worker: `docker compose down`  
2. Restore Postgres: `gunzip -c backup.sql.gz | psql ...`  
3. Restore upload volume  
4. Run migrations if version changed: `make migrate`  
5. Start stack: `docker compose up -d`  
6. Smoke test: `make test-integration` (or health + login)  
7. Verify audit chain (see §2.3)

---

## 4. Failure scenarios

| Scenario | Response |
|----------|----------|
| Single container crash | `docker compose restart api worker` |
| DB corruption | Restore latest pg_dump; accept RPO window |
| Full site loss | Failover to warm standby per §5 |
| Ransomware | Restore from immutable offline backup; rotate `AUTH_SECRET_KEY` |

---

## 5. Warm standby (optional)

- Replica Postgres streaming replication to `{DR_SITE}`  
- Periodic rsync of uploads to DR site  
- Document failover DNS / VIP owned by `{CUSTOMER}`

---

## 6. Communication

| Role | Contact |
|------|---------|
| Incident commander | `{CONTACT}` |
| DPO | `{CONTACT}` |
| Vendor support | Internal engineering lead |

Reference `docs/compliance/INCIDENT_RESPONSE.md` for security incidents.

---

## 7. Test schedule

| Test | Frequency |
|------|-----------|
| Backup verification (restore to staging) | Quarterly |
| Full DR drill | Annually |
| Audit verify after restore | Each drill |

---

## 8. WORM / legal hold notes

- Legal holds survive normal delete paths — DR restore must preserve `legal_holds` and `audit_events` tables intact.  
- Sealed audit bundles (9E filesystem WORM) should be included in off-site backup when `WORM_BACKEND=filesystem`.

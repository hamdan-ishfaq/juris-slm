# BEWEIS — Demo Walkthrough

This script walks through the core product in 10 minutes.
Run it locally at `http://localhost:8001` after `docker compose up -d`.

---

## Setup

```bash
docker compose up -d
cd frontend && npm run build
```

Create the owner account (first time only):

```bash
# Register
curl -s -X POST http://localhost:8001/auth/register \
  -H "Content-Type: application/json" \
  -d '{"email":"owner@beweis.com","password":"OwnerSecret123!"}'

# Promote to owner
docker exec juris_full_project-db-1 psql -U juris -d juris_db \
  -c "UPDATE users SET role='OWNER' WHERE email='owner@beweis.com';"
```

---

## Scene 1 — Login and role visibility

1. Open `http://localhost:8001`
2. Log in as `owner@beweis.com` / `OwnerSecret123!`
3. Notice the sidebar shows **Chat**, **Upload**, **Diagnostics**, **Users** — owner sees everything

---

## Scene 2 — Upload a level_1 document (visible to everyone)

1. Go to **Upload**
2. Select clearance level: **General — level 1**
3. Upload any PDF
4. Confirm success toast

---

## Scene 3 — Upload a level_2 document (legal team only)

1. Still on **Upload**
2. Select clearance level: **Legal team — level 2**
3. Upload a second PDF (or the same one)
4. Confirm success

---

## Scene 4 — Query as owner (sees both documents)

1. Go to **Chat**
2. Ask a question that relates to content from both documents
3. Owner gets answers drawing from level_1 and level_2 content

---

## Scene 5 — Create a regular user and query as them

In a second browser (or incognito):

```bash
curl -s -X POST http://localhost:8001/auth/register \
  -H "Content-Type: application/json" \
  -d '{"email":"staff@beweis.com","password":"StaffPass123!"}'
```

1. Log in as `staff@beweis.com`
2. Ask the same question
3. Sidebar only shows **Chat** and **Upload** — no Diagnostics, no Users
4. Answer is scoped to level_1 content only — level_2 document does not appear

**This is the core RBAC demonstration.** Same query, different answer based on clearance.

---

## Scene 6 — Manage Users (owner only)

1. Back in owner session
2. Go to **Manage Users**
3. Promote `staff@beweis.com` to Admin
4. Re-login as staff — they now see level_1 + level_2 content in chat

---

## Scene 7 — Run Diagnostics

1. Go to **Diagnostics**
2. Click Run Evaluation
3. Watch the 10-case test suite execute
4. Confirm 9/10 pass (test 4 is a known retrieval edge case, not a code bug)

---

## What this demonstrates

| Capability | Evidence |
|---|---|
| JWT authentication | Login/logout, protected routes |
| Role-based navigation | Owner sees 4 nav items, user sees 2 |
| Document access tiers | level_2 doc hidden from regular user |
| Hybrid retrieval | Answers grounded in uploaded documents |
| Prompt hardening | Try asking for system instructions — refused |
| Audit trail | QueryTrace written per query in PostgreSQL |
| Owner governance | User promotion, diagnostics, evaluation |

---

## Cleanup

```bash
docker compose down -v   # removes containers and volumes
```

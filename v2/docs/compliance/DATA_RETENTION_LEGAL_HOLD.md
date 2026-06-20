# Data Retention & Legal Hold Policy (Template)

**Owner:** Data Protection Officer · **Review:** Annual

---

## Purpose

Define retention periods and legal hold procedures for `{CUSTOMER}` JurisGuard deployment.

---

## Default retention

| Data class | Retention | Deletion method |
|------------|-----------|-----------------|
| Matter documents | Contract term + {N} years | Document delete API / erasure worker |
| Chat threads | {N} months | Manual / future retention job |
| Audit events | {N} years (immutable) | No routine delete; WORM chain |
| User accounts | Employment + {N} days | SCIM deprovision / admin disable |

---

## Legal hold

1. Only `org_admin` or `owner` may place/release holds (API + Matters UI).  
2. Holds block matter/document **delete** and **erasure**; export configurable via `LEGAL_HOLD_ALLOW_EXPORT`.  
3. All hold actions appear in audit log (`legal_hold_place`, `legal_hold_release`).

---

## Exceptions

Regulatory investigation, litigation, or supervisory authority request → hold until counsel releases.

---

## Roles

| Role | Responsibility |
|------|----------------|
| DPO | Approve hold/release for GDPR matters |
| Legal counsel | Scope of hold |
| Org admin | Execute hold in product |

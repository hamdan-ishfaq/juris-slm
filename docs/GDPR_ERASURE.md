# Erasure requests

What deleting removes, what stays and why, and the steps for a request under GDPR Article 17. Each step was checked against
the code and the running system on 2026-11-13.

## A document or a matter

`DELETE /api/v1/matters/{id}/documents/{doc_id}`, or `DELETE /api/v1/matters/{id}` for a whole matter, as a matter owner:

| Removed | Kept |
|---|---|
| The uploaded file | An audit event recording the deletion (ids, not content) |
| Its text chunks and their embeddings | |
| Its routing description (D-015) | |
| Its contract graph nodes and edges | |
| Contract workspace versions and annotations | |

Until 2026-11-13 the uploaded file stayed on disk after deletion; it is now removed, and only from the uploads folder.

**Also check:** answers already given that quote the document stay in users' chat threads, and in the answer cache for up
to an hour (`QUERY_CACHE_TTL_SECONDS`). To clear the cache at once:

```bash
docker compose exec cache sh -c "redis-cli --scan --pattern 'juris:qa:*' | xargs -r redis-cli del"
```

## A person

`DELETE /api/v1/admin/users/{user_id}`, as the organisation's owner:

| Removed | Kept |
|---|---|
| Their chat threads, messages and answer feedback | Audit events, pointing at an id that no longer names anyone |
| Their sessions (refresh tokens) | Matters they created, now owned by the owner who deleted them |
| Their email and password: the account is anonymised and disabled | |

Audit events stay because each one's hash covers its user id, so deleting or editing them would break the chain that
`/api/v1/audit/verify` checks. Chat audit events hold a hash of each question, not its text, unless `AUDIT_LOG_ANSWERS`
is on; with it on they hold the first 500 characters of each answer, which this process doesn't remove. Until 2026-11-13
this endpoint failed with a 500 for any user who had used the product.

Personal data inside a contract (a named counterparty, an employee in an agreement) is part of that document: erase it by
deleting the document, or by replacing it with a redacted version.

## Steps for a request

1. Find what concerns the person: their account, and documents that name them (search the matters they belong to).
2. Delete those documents, or replace them with redacted copies.
3. Delete the user, if the request covers their account.
4. Clear the answer cache.
5. Check `GET /api/v1/audit/verify` is still valid, and record the request and what was done.
6. Backups taken before the request still hold the data; let them expire on their normal schedule, or restore and
   repeat these steps if they are kept long.

# Backup and restore

What has to be backed up, how, and how to check a restore. Tested on 2026-11-13: a dump of the live database (24 MB,
3 s) restored into a fresh database with identical row counts for users, audit events, document chunks, citation graph
references and documents.

## What holds state

| Store | Contents | Back up? |
|---|---|---|
| Postgres `juris_db` (volume `postgres_data`) | Users, matters, documents' text and embeddings, chats, audit log, citation graph | **Yes** |
| Volume `uploads_data` | The original uploaded files | **Yes** |
| `data/models`, `data/raw/law_corpus` | Model weights and the law texts | Once; they can be fetched again (`make models`, `make download-law`) |
| Redis (`cache`) | Answer cache and job state, kept an hour at most | No |
| Ollama models | qwen3:8b, qwen2.5:3b | No; `ollama pull` again |

## Back up

```bash
docker compose exec -T db pg_dump -U juris -Fc juris_db > juris_db_$(date +%F).dump
docker run --rm -v jurisguard_uploads_data:/u -v "$PWD":/out alpine tar czf /out/uploads_$(date +%F).tgz -C /u .
```

Keep both off the machine. The dump holds personal data and contracts, so store it with the same care as the system.

## Restore

```bash
docker compose up -d db
docker compose exec -T db createdb -U juris juris_db            # if it doesn't exist
docker compose exec -T db pg_restore -U juris -d juris_db --clean --if-exists --no-owner < juris_db_YYYY-MM-DD.dump
docker run --rm -v jurisguard_uploads_data:/u -v "$PWD":/in alpine tar xzf /in/uploads_YYYY-MM-DD.tgz -C /u
make up && make check-llm-gpu
```

## Check the restore

1. `GET /api/v1/audit/verify` as an org admin: `valid` must be true. A broken chain means the dump or the restore changed
   audit rows.
2. `GET /api/v1/corpus/stats`: the law chunk count should match the backup (4,129 for the four statutes).
3. Ask one law question and open one uploaded document.
4. `make e2e` against the restored stack.

#!/usr/bin/env bash
# Reproduce the LegalBench-RAG table: fetch data, ingest once, run every mode, score the dev split.
# Set BENCH_GPU=0 on machines with no NVIDIA GPU. Results go to eval/reports/bench/.
set -euo pipefail
cd "$(dirname "$0")/.."

PY=.venv/bin/python
HARNESS=eval/legalbench/legalbench.py
COMPOSE=(docker compose -f docker-compose.yml)
[[ "${BENCH_GPU:-1}" == 1 ]] && COMPOSE+=(-f docker-compose.gpu.yml)
BENCH_DB=postgresql+asyncpg://juris:juris_password@db:5432/juris_bench
IN_API=("${COMPOSE[@]}" run --rm --no-deps -T -e "DATABASE_URL=$BENCH_DB" -v "$PWD/eval:/app/eval" api)

"${COMPOSE[@]}" up -d db cache
until "${COMPOSE[@]}" exec -T db pg_isready -U juris >/dev/null 2>&1; do sleep 2; done

[[ -d data/benchmarks/legalbench/data/corpus ]] || "$PY" "$HARNESS" fetch

"${COMPOSE[@]}" exec -T db sh -c \
  "psql -U juris -d postgres -Atc \"SELECT 1 FROM pg_database WHERE datname='juris_bench'\" | grep -q 1 \
   || createdb -U juris juris_bench"
"${IN_API[@]}" alembic upgrade head

CHUNKS=$("${COMPOSE[@]}" exec -T db psql -U juris -d juris_bench -Atc "SELECT count(*) FROM document_chunks")
if [[ "$CHUNKS" == 0 || ! -f data/benchmarks/legalbench/chunks.jsonl ]]; then
  "${IN_API[@]}" python eval/legalbench/legalbench.py ingest
fi

RUN=${BENCH_RUN:-latest}
"${IN_API[@]}" python eval/legalbench/legalbench.py run --run "$RUN"
"$PY" "$HARNESS" run --run "$RUN" --modes bm25
"$PY" "$HARNESS" score --run "$RUN" --split dev --output eval/reports/bench/results.json

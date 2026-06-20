#!/bin/sh
set -eu

UPLOADS_DIR="/app/src/data/uploads"
CACHE_DIR="/home/juris/.cache/huggingface"

mkdir -p "$UPLOADS_DIR" "$CACHE_DIR"

run_migrations() {
  if [ -f /app/alembic.ini ]; then
    echo "Running database migrations..."
    alembic upgrade head
  fi
}

# Named volumes may be root-owned from prior root containers — fix once at start.
if [ "$(id -u)" = "0" ]; then
  python -c "import slowapi" 2>/dev/null || pip install --no-cache-dir 'slowapi>=0.1.9,<0.2.0'
  chown -R juris:juris "$UPLOADS_DIR" "$CACHE_DIR" 2>/dev/null || true
  if [ "${1:-}" = "uvicorn" ]; then
    gosu juris sh -c "cd /app && alembic upgrade head"
  fi
  exec gosu juris "$@"
fi

if [ "${1:-}" = "uvicorn" ]; then
  run_migrations
fi

exec "$@"

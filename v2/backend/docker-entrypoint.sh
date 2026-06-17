#!/bin/sh
set -eu

UPLOADS_DIR="/app/src/data/uploads"
CACHE_DIR="/home/juris/.cache/huggingface"

mkdir -p "$UPLOADS_DIR" "$CACHE_DIR"

# Named volumes may be root-owned from prior root containers — fix once at start.
if [ "$(id -u)" = "0" ]; then
  chown -R juris:juris "$UPLOADS_DIR" "$CACHE_DIR" 2>/dev/null || true
  exec gosu juris "$@"
fi

exec "$@"

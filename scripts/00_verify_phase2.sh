#!/usr/bin/env bash
# Phase 2 — verify Docker stack (run from v2/)
set -euo pipefail
cd "$(dirname "$0")/.."

echo "=== Phase 2 verify ==="

if [[ ! -f .env ]]; then
  echo "[WARN] Copy .env.example to .env and set TRAINING_DIR"
fi

echo "[1] docker compose config..."
docker compose config -q

echo "[2] Starting db + cache + ollama + api..."
docker compose up -d --build

echo "[3] Waiting for health..."
sleep 8

echo "[4] API health..."
curl -sf http://localhost:8002/health | head -c 200
echo ""

echo "[5] API status (training manifest + ollama)..."
curl -sf http://localhost:8002/api/v1/status | python3 -m json.tool | head -40

echo ""
echo "Phase 2 stack up:"
echo "  API:    http://localhost:8002"
echo "  Docs:   http://localhost:8002/docs"
echo "  Ollama: http://localhost:11434"
echo ""
echo "Pull base model: docker compose exec ollama ollama pull phi3.5"

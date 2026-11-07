#!/usr/bin/env bash
# Verify GPU stack for JurisGuard air-gap (Ollama + optional CUDA embed/rerank).
set -euo pipefail
cd "$(dirname "$0")/.."

echo "=== JurisGuard GPU stack verification ==="
PASS=0
WARN=0

check() {
  local label="$1"
  shift
  if "$@" >/dev/null 2>&1; then
    echo "[OK]   $label"
    PASS=$((PASS + 1))
  else
    echo "[WARN] $label"
    WARN=$((WARN + 1))
  fi
}

if command -v nvidia-smi >/dev/null 2>&1; then
  echo ""
  echo "GPU:"
  nvidia-smi --query-gpu=name,driver_version,memory.total --format=csv,noheader
  PASS=$((PASS + 1))
else
  echo "[WARN] nvidia-smi not found — embed/rerank and Ollama will use CPU unless Ollama has GPU elsewhere"
  WARN=$((WARN + 1))
fi

echo ""
echo "Ollama (recommended: native host with GPU):"
if command -v ollama >/dev/null 2>&1; then
  echo "[OK]   ollama CLI installed"
  PASS=$((PASS + 1))
  if curl -sf "${OLLAMA_BASE_URL:-http://localhost:11434}/api/tags" >/dev/null 2>&1; then
    echo "[OK]   Ollama API reachable at ${OLLAMA_BASE_URL:-http://localhost:11434}"
    PASS=$((PASS + 1))
    if ollama list 2>/dev/null | grep -qi mistral; then
      echo "[OK]   Mistral model present"
      PASS=$((PASS + 1))
    else
      echo "[WARN] mistral not pulled — run: bash scripts/setup_ollama_gpu.sh"
      WARN=$((WARN + 1))
    fi
  else
    echo "[WARN] Ollama not running — start with: ollama serve"
    WARN=$((WARN + 1))
  fi
else
  echo "[WARN] ollama CLI missing — run scripts/setup_ollama_gpu.sh"
  WARN=$((WARN + 1))
fi

echo ""
echo "Docker API (CUDA embed/rerank):"
if curl -sf http://localhost:8002/health >/dev/null 2>&1; then
  echo "[OK]   API health"
  PASS=$((PASS + 1))
  TOKEN="${JURIS_TOKEN:-}"
  if [[ -z "$TOKEN" ]] && [[ -f .env ]]; then
  DEV_EMAIL=$(grep -E '^DEV_MASTER_EMAIL=' .env 2>/dev/null | cut -d= -f2- | tr -d '"' || true)
  DEV_PASS=$(grep -E '^DEV_MASTER_PASSWORD=' .env 2>/dev/null | cut -d= -f2- | tr -d '"' || true)
  if [[ -n "$DEV_EMAIL" && -n "$DEV_PASS" ]]; then
    TOKEN=$(curl -sf -X POST http://localhost:8002/api/v1/auth/login \
      -H 'Content-Type: application/json' \
      -d "{\"email\":\"$DEV_EMAIL\",\"password\":\"$DEV_PASS\"}" \
      | python3 -c 'import sys,json; print(json.load(sys.stdin).get("access_token",""))' 2>/dev/null || true)
  fi
  fi
  if [[ -n "$TOKEN" ]]; then
    HW_JSON=$(curl -sf -H "Authorization: Bearer $TOKEN" http://localhost:8002/api/v1/status \
      | python3 -c 'import sys,json; h=json.load(sys.stdin).get("hardware",{}); print(json.dumps(h))' 2>/dev/null || true)
    if [[ -n "$HW_JSON" ]]; then
      CUDA=$(echo "$HW_JSON" | python3 -c 'import sys,json; print(json.load(sys.stdin).get("cuda_available",False))')
      EMBED=$(echo "$HW_JSON" | python3 -c 'import sys,json; print(json.load(sys.stdin).get("embedding_device","?"))')
      if [[ "$CUDA" == "True" ]]; then
        echo "[OK]   CUDA active in API — embedding_device=$EMBED"
        PASS=$((PASS + 1))
      else
        echo "[WARN] API reports cuda_available=false (CPU PyTorch image?) — run: make up-gpu"
        WARN=$((WARN + 1))
      fi
    fi
  else
    echo "       Set JURIS_TOKEN or DEV_MASTER_* in .env to check cuda_available"
  fi
else
  echo "[WARN] API not up at :8002 — run: make up or make up-gpu"
  WARN=$((WARN + 1))
fi

if docker info 2>/dev/null | grep -qi nvidia; then
  echo "[OK]   Docker NVIDIA runtime available"
  PASS=$((PASS + 1))
  echo "       Enable CUDA embed/rerank: make up-gpu"
else
  echo "[INFO] Docker NVIDIA runtime not detected — install nvidia-container-toolkit (WSL2)"
fi

echo ""
echo "Summary: $PASS checks passed, $WARN warnings"
echo ""
echo "Recommended RTX 4050 6GB profile:"
echo "  1. bash scripts/setup_ollama_gpu.sh   # Mistral-7B Q4 on GPU"
echo "  2. cp .env.airgap.example .env"
echo "  3. make up"
echo "  Optional CUDA retrieval: make gpu-build && make gpu-up"
exit 0

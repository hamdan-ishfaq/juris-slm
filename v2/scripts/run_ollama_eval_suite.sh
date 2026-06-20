#!/usr/bin/env bash
# Run full eval suite with Ollama (no OpenRouter) + GPU stack
set -euo pipefail
cd "$(dirname "$0")/.."

echo "=== Ollama model check ==="
if ! command -v ollama >/dev/null 2>&1; then
  echo "Installing Ollama..."
  curl -fsSL https://ollama.com/install.sh | sh
fi
export OLLAMA_NUM_GPU="${OLLAMA_NUM_GPU:-99}"
ollama pull phi3.5 || { echo "Failed to pull phi3.5"; exit 1; }
ollama list | grep -i phi3 || true

echo "=== GPU stack up ==="
make up-gpu

echo "=== Waiting for API + CUDA ==="
sleep 10
bash scripts/verify_gpu_stack.sh || true

echo "=== Full eval suite (Ollama LLM) ==="
export LLM_PROVIDER=ollama
export OLLAMA_MODEL=phi3.5
export OLLAMA_AUX_MODEL=phi3.5
unset OPENROUTER_API_KEY 2>/dev/null || true

REPORT_DIR=eval/reports
mkdir -p "$REPORT_DIR"
STAMP=$(date -u +%Y%m%dT%H%M%SZ)

make eval-offline 2>&1 | tee "$REPORT_DIR/eval_offline_${STAMP}.log"
make eval-logical 2>&1 | tee "$REPORT_DIR/eval_logical_${STAMP}.log"
make eval-ragas 2>&1 | tee "$REPORT_DIR/eval_ragas_${STAMP}.log"
make eval-latency 2>&1 | tee "$REPORT_DIR/eval_latency_${STAMP}.log"

echo "=== Done — reports in $REPORT_DIR ==="
ls -la "$REPORT_DIR"/*latest* 2>/dev/null || true

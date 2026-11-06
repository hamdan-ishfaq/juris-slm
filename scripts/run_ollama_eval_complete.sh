#!/usr/bin/env bash
# Full Ollama eval — continues all suites even if one reports failures; writes combined summary.
set -uo pipefail
cd "$(dirname "$0")/.."

export LLM_PROVIDER=ollama
export OLLAMA_MODEL="${OLLAMA_MODEL:-mistral:7b-instruct-v0.3-q4_K_M}"
export OLLAMA_AUX_MODEL="${OLLAMA_AUX_MODEL:-qwen2.5:3b}"
export EVAL_CHAT_TIMEOUT="${EVAL_CHAT_TIMEOUT:-1200}"
export EVAL_FIXTURE_TIMEOUT="${EVAL_FIXTURE_TIMEOUT:-600}"
unset OPENROUTER_API_KEY 2>/dev/null || true

REPORT_DIR=eval/reports
mkdir -p "$REPORT_DIR"
STAMP=$(date -u +%Y%m%dT%H%M%SZ)
LOG="$REPORT_DIR/ollama_eval_complete_${STAMP}.log"

exec > >(tee -a "$LOG") 2>&1

echo "=== Ollama full eval started $(date -u -Iseconds) ==="
echo "MODEL=$OLLAMA_MODEL EVAL_CHAT_TIMEOUT=$EVAL_CHAT_TIMEOUT"

if ! curl -sf http://localhost:8002/health >/dev/null; then
  echo "API not up — run: make up-gpu"
  exit 1
fi
if ! curl -sf http://localhost:11434/api/tags >/dev/null; then
  echo "Ollama not reachable on :11434"
  exit 1
fi

OFFLINE_RC=0 LOGICAL_RC=0 RAGAS_RC=0 LATENCY_RC=0

make eval-offline || OFFLINE_RC=$?

echo "Pre-warming contract fixtures (upload + ingest)..."
.venv/bin/python scripts/warm_eval_fixtures.py || true

.venv/bin/python scripts/run_logical_eval.py --all --no-baseline-gate \
  --report eval/reports/logical_latest.json || LOGICAL_RC=$?
.venv/bin/python scripts/run_ragas_eval.py --subset 15 --no-baseline-gate \
  --report eval/reports/ragas_latest.json || RAGAS_RC=$?
.venv/bin/python scripts/run_latency_bench.py --chat-runs 5 --warn-only \
  --report eval/reports/latency_latest.json || LATENCY_RC=$?

.venv/bin/python scripts/build_ollama_eval_summary.py

echo ""
echo "=== Suite exit codes: offline=$OFFLINE_RC logical=$LOGICAL_RC ragas=$RAGAS_RC latency=$LATENCY_RC ==="
echo "Log: $LOG"
echo "Summary: eval/reports/ollama_eval_summary_latest.json"

if [[ "$OFFLINE_RC" -ne 0 ]]; then exit "$OFFLINE_RC"; fi
exit 0

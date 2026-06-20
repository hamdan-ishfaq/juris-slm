#!/usr/bin/env bash
# Wait for Ollama phi3.5, verify chat, run full eval suite (no OpenRouter).
set -euo pipefail
cd "$(dirname "$0")/.."

OLLAMA_URL="${OLLAMA_URL:-http://localhost:11434}"
MODEL="${OLLAMA_MODEL:-phi3.5}"
REPORT_DIR="eval/reports"
STAMP=$(date -u +%Y%m%dT%H%M%SZ)
LOG="$REPORT_DIR/ollama_eval_monitor_${STAMP}.log"
SUMMARY="$REPORT_DIR/ollama_eval_summary_${STAMP}.json"

mkdir -p "$REPORT_DIR"
exec > >(tee -a "$LOG") 2>&1

log() { echo "[$(date -u +%H:%M:%S)] $*"; }

has_model() {
  curl -sf "$OLLAMA_URL/api/tags" | python3 -c "
import sys, json
models = [m.get('name','') for m in json.load(sys.stdin).get('models',[])]
target = '$MODEL'
print('yes' if any(target in m or m.startswith(target) for m in models) else 'no')
" 2>/dev/null | grep -q yes
}

wait_for_ollama() {
  for i in $(seq 1 30); do
    if curl -sf "$OLLAMA_URL/api/tags" >/dev/null 2>&1; then
      return 0
    fi
    log "Waiting for Ollama API ($i/30)..."
    sleep 5
  done
  log "ERROR: Ollama API not reachable at $OLLAMA_URL"
  return 1
}

pull_model() {
  if has_model; then
    log "Model $MODEL already present"
    return 0
  fi
  log "Pulling $MODEL via Ollama HTTP API (may take 10-30 min)..."
  curl -sfN "$OLLAMA_URL/api/pull" -d "{\"name\":\"$MODEL\"}" | while IFS= read -r line; do
    status=$(echo "$line" | python3 -c "import sys,json; d=json.load(sys.stdin); print(d.get('status',''))" 2>/dev/null || echo "")
    if [ -n "$status" ]; then
      pct=$(echo "$line" | python3 -c "import sys,json; d=json.load(sys.stdin); c=d.get('completed'); t=d.get('total'); print(f'{100*c//t}%' if c and t else '')" 2>/dev/null || echo "")
      [ -n "$pct" ] && log "  pull: $status $pct" || log "  pull: $status"
    fi
    echo "$line" >> "$REPORT_DIR/phi35_pull_${STAMP}.jsonl"
  done
  has_model
}

wait_for_model() {
  local max_wait="${1:-3600}"
  local elapsed=0
  while [ "$elapsed" -lt "$max_wait" ]; do
    if has_model; then
      log "Model $MODEL is ready"
      curl -sf "$OLLAMA_URL/api/tags" | python3 -m json.tool
      return 0
    fi
    if [ $((elapsed % 60)) -eq 0 ]; then
      log "Still waiting for $MODEL (${elapsed}s elapsed)..."
    fi
    sleep 15
    elapsed=$((elapsed + 15))
  done
  log "ERROR: Timed out waiting for $MODEL after ${max_wait}s"
  return 1
}

verify_chat() {
  log "Verifying API chat with Ollama..."
  docker compose -f docker-compose.yml -f docker-compose.gpu.yml up -d api worker >/dev/null 2>&1 || true
  sleep 30
  for i in $(seq 1 40); do
    if curl -sf http://localhost:8002/health >/dev/null 2>&1; then break; fi
    sleep 3
  done
  TOKEN=$(curl -sf -X POST http://localhost:8002/api/v1/auth/login \
    -H 'Content-Type: application/json' \
    -d '{"email":"devmaster@example.com","password":"DevMasterPass123!"}' \
    | python3 -c "import sys,json; print(json.load(sys.stdin)['access_token'])")
  HTTP=$(curl -s -o /tmp/chat_test.json -w "%{http_code}" -X POST http://localhost:8002/api/v1/chat \
    -H "Authorization: Bearer $TOKEN" \
    -H 'Content-Type: application/json' \
    -d '{"message":"What is GDPR Article 6 lawful basis?","use_law_corpus":true}' \
    --max-time 900)
  if [ "$HTTP" = "200" ]; then
    log "Chat OK: $(python3 -c "import json; print(json.load(open('/tmp/chat_test.json')).get('answer','')[:120])")..."
    return 0
  fi
  log "ERROR: Chat HTTP $HTTP — $(cat /tmp/chat_test.json 2>/dev/null | head -c 200)"
  return 1
}

run_evals() {
  export LLM_PROVIDER=ollama
  export OLLAMA_MODEL="$MODEL"
  export OLLAMA_AUX_MODEL="$MODEL"
  unset OPENROUTER_API_KEY 2>/dev/null || true

  OFFLINE_OK=0 LOGICAL_OK=0 RAGAS_OK=0 LATENCY_OK=0

  log "=== eval-offline ==="
  if make eval-offline 2>&1 | tee "$REPORT_DIR/eval_offline_${STAMP}.log"; then OFFLINE_OK=1; fi

  log "=== eval-logical ==="
  if make eval-logical 2>&1 | tee "$REPORT_DIR/eval_logical_${STAMP}.log"; then LOGICAL_OK=1; fi

  log "=== eval-ragas ==="
  if make eval-ragas 2>&1 | tee "$REPORT_DIR/eval_ragas_${STAMP}.log"; then RAGAS_OK=1; fi

  log "=== eval-latency ==="
  if make eval-latency 2>&1 | tee "$REPORT_DIR/eval_latency_${STAMP}.log"; then LATENCY_OK=1; fi

  python3 - <<PY
import json
from pathlib import Path
summary = {
  "timestamp": "$STAMP",
  "model": "$MODEL",
  "llm_provider": "ollama",
  "offline_ok": bool($OFFLINE_OK),
  "logical_ok": bool($LOGICAL_OK),
  "ragas_ok": bool($RAGAS_OK),
  "latency_ok": bool($LATENCY_OK),
}
for name in ("logical", "ragas", "latency"):
    p = Path("eval/reports") / f"{name}_latest.json"
    if p.exists():
        summary[name] = json.loads(p.read_text())
p = Path("eval/reports/logical_latest.json")
if p.exists():
    summary["logical_pass_rate"] = json.loads(p.read_text()).get("pass_rate")
Path("$SUMMARY").write_text(json.dumps(summary, indent=2))
print(json.dumps(summary, indent=2))
PY
  log "Summary written to $SUMMARY"
}

main() {
  log "=== Ollama eval monitor started ==="
  log "Model: $MODEL | Ollama: $OLLAMA_URL"

  wait_for_ollama
  if ! has_model; then
    pull_model || true
  fi
  wait_for_model 3600

  log "Recreating API/worker with Ollama env..."
  docker compose -f docker-compose.yml -f docker-compose.gpu.yml up -d --force-recreate api worker
  sleep 15

  verify_chat || { log "Chat verification failed — aborting eval suite"; exit 1; }

  run_evals
  log "=== Ollama eval monitor complete ==="
}

main "$@"

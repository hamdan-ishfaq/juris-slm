#!/usr/bin/env bash
# Fresh-stack restart + full regression + performance recording.
# Runs every gate even on failure; exits non-zero if any gate fails.
set -uo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"

TS="$(date -u +%Y%m%dT%H%M%SZ)"
REPORT_DIR="$ROOT/eval/reports"
LOG="$REPORT_DIR/brutal_gate_${TS}.log"
MASTER="$REPORT_DIR/brutal_gate_latest.json"
mkdir -p "$REPORT_DIR"

FRESH="${BRUTAL_FRESH:-1}"
SKIP_UI="${BRUTAL_SKIP_UI:-0}"
CHAT_RUNS="${BRUTAL_CHAT_RUNS:-3}"

exec > >(tee -a "$LOG") 2>&1

echo "=============================================="
echo " JurisGuard V2 — BRUTAL GATE"
echo " Timestamp: $TS"
echo " Log: $LOG"
echo "=============================================="

GATE_JSON="[]"
OVERALL_RC=0

record_gate() {
  local name="$1"
  local rc="$2"
  local duration_ms="$3"
  local detail="${4:-}"
  GATE_JSON="$(python3 - <<PY
import json
gates = json.loads('''$GATE_JSON''')
gates.append({
    "name": """$name""",
    "ok": $([ "$rc" -eq 0 ] && echo True || echo False),
    "duration_ms": $duration_ms,
    "detail": """${detail//\"/\\\"}""",
})
print(json.dumps(gates))
PY
)"
  if [[ "$rc" -ne 0 ]]; then
    OVERALL_RC=1
    echo ">>> GATE FAIL: $name (rc=$rc)"
  else
    echo ">>> GATE PASS: $name (${duration_ms}ms)"
  fi
}

run_gate() {
  local name="$1"
  shift
  echo ""
  echo "---------- $name ----------"
  local t0
  t0="$(python3 -c 'import time; print(int(time.time()*1000))')"
  local rc=0
  "$@" || rc=$?
  local t1
  t1="$(python3 -c 'import time; print(int(time.time()*1000))')"
  local dur=$((t1 - t0))
  record_gate "$name" "$rc" "$dur" ""
  return 0
}

wall_t0="$(python3 -c 'import time; print(int(time.time()*1000))')"

if [[ "$FRESH" == "1" ]]; then
  run_gate "fresh_down_volumes" docker compose down -v || true
  run_gate "docker_build_api_worker" docker compose build api worker
  run_gate "docker_up_db_cache" docker compose up -d db cache
  echo "Waiting for Postgres..."
  for i in $(seq 1 30); do
    if docker compose exec -T db pg_isready -U juris >/dev/null 2>&1; then
      echo "Postgres ready after ${i} attempts"
      break
    fi
    sleep 2
  done
  run_gate "alembic_migrate" docker compose run --rm --no-deps api alembic upgrade head
  run_gate "docker_up" docker compose up -d --remove-orphans
  echo "Waiting for API health..."
  API_OK=0
  for i in $(seq 1 45); do
    if curl -sf http://localhost:8002/health >/dev/null 2>&1; then
      API_OK=1
      echo "API healthy after ${i} attempts"
      break
    fi
    sleep 3
  done
  if [[ "$API_OK" != "1" ]]; then
    echo "API not ready — restarting api container"
    docker compose restart api || true
    for i in $(seq 1 20); do
      if curl -sf http://localhost:8002/health >/dev/null 2>&1; then
        API_OK=1
        break
      fi
      sleep 3
    done
  fi
  if [[ "$API_OK" == "1" ]]; then
    curl -sf http://localhost:8002/health | python3 -m json.tool
  else
    echo "ERROR: API not ready after bootstrap"
    docker compose logs api --tail 40 || true
    OVERALL_RC=1
  fi
  run_gate "fix_upload_perms" docker compose run --user root --rm worker chown -R juris:juris /app/src/data/uploads
  echo "Ingesting law corpus (fresh DB)..."
  run_gate "ingest_law" docker compose exec -T api python /app/src/ingest_law.py --force
else
  echo "BRUTAL_FRESH=0 — skipping volume wipe; using running stack"
fi

run_gate "verify_gpu_stack" bash scripts/verify_gpu_stack.sh || true

run_gate "test_unit" make test-unit
run_gate "test_integration" bash -c 'cd backend && PYTHONPATH=src:tests ../.venv/bin/pytest tests/ -v -m integration --tb=short --durations=15'

E2E_REPORT="$REPORT_DIR/e2e_functional_${TS}.json"
run_gate "e2e_functional" .venv/bin/python scripts/e2e_functional_test.py --report "$E2E_REPORT"

run_gate "eval_offline" make eval-offline
run_gate "eval_logical" .venv/bin/python scripts/run_logical_eval.py --all --no-baseline-gate

LATENCY_REPORT="$REPORT_DIR/latency_${TS}.json"
run_gate "eval_latency" .venv/bin/python scripts/run_latency_bench.py --chat-runs "$CHAT_RUNS" --report "$LATENCY_REPORT"

if [[ "$SKIP_UI" != "1" ]]; then
  run_gate "ui_build" make ui-build
  run_gate "playwright_e2e" make ui-e2e || true
else
  echo "Skipping UI gates (BRUTAL_SKIP_UI=1)"
fi

wall_t1="$(python3 -c 'import time; print(int(time.time()*1000))')"
WALL_MS=$((wall_t1 - wall_t0))

python3 - <<PY
import json
from datetime import datetime, timezone
from pathlib import Path

root = Path("$ROOT")
report_dir = root / "eval" / "reports"
ts = "$TS"

def load_json(p):
    p = Path(p)
    if p.is_file():
        return json.loads(p.read_text())
    return None

gates = json.loads('''$GATE_JSON''')
passed = sum(1 for g in gates if g.get("ok"))
failed = sum(1 for g in gates if not g.get("ok"))

master = {
    "suite": "brutal_gate",
    "timestamp": datetime.now(timezone.utc).isoformat(),
    "run_id": ts,
    "wall_ms": $WALL_MS,
    "summary": {"gates_passed": passed, "gates_failed": failed, "gates_total": len(gates)},
    "gates": gates,
    "artifacts": {
        "log": str(report_dir / f"brutal_gate_{ts}.log"),
        "e2e": str(report_dir / f"e2e_functional_{ts}.json"),
        "latency": str(report_dir / f"latency_{ts}.json"),
        "logical": str(report_dir / "logical_latest.json"),
        "offline": str(report_dir / "offline_latest.json"),
    },
    "e2e": load_json(report_dir / f"e2e_functional_{ts}.json"),
    "latency": load_json(report_dir / f"latency_{ts}.json"),
    "logical": load_json(report_dir / "logical_latest.json"),
    "offline": load_json(report_dir / "offline_latest.json"),
}

out = report_dir / "brutal_gate_latest.json"
out.write_text(json.dumps(master, indent=2), encoding="utf-8")
(report_dir / f"brutal_gate_{ts}.json").write_text(json.dumps(master, indent=2), encoding="utf-8")
print(f"\nMaster report: {out}")
print(json.dumps(master["summary"], indent=2))
if master.get("latency") and master["latency"].get("results"):
    print("\nLatency results:")
    print(json.dumps(master["latency"]["results"], indent=2))
if master.get("e2e") and master["e2e"].get("phase_timings_ms"):
    print("\nE2E phase timings (ms):")
    print(json.dumps(master["e2e"]["phase_timings_ms"], indent=2))
PY

echo ""
echo "=============================================="
if [[ "$OVERALL_RC" -eq 0 ]]; then
  echo " BRUTAL GATE: ALL PASSED (${WALL_MS}ms wall)"
else
  echo " BRUTAL GATE: FAILURES (${WALL_MS}ms wall) — see $LOG"
fi
echo " Report: $MASTER"
echo "=============================================="

exit "$OVERALL_RC"

#!/usr/bin/env bash
# Full eval profile for air-gap (Ollama-only) deployments — strict gate ≥95% logical pass.
set -euo pipefail
cd "$(dirname "$0")/.."

export LLM_PROVIDER="${LLM_PROVIDER:-ollama}"
export LLM_AUX_PROVIDER="${LLM_AUX_PROVIDER:-ollama}"
export CI_SKIP_LLM="${CI_SKIP_LLM:-0}"
MIN_PASS="${AIRGAP_MIN_LOGICAL_PASS:-0.95}"

echo "Air-gap eval profile: LLM_PROVIDER=$LLM_PROVIDER (min logical pass: ${MIN_PASS})"

make eval-offline

LOGICAL_RC=0
make eval-logical || LOGICAL_RC=$?

REPORT="eval/reports/logical_latest.json"
if [[ -f "$REPORT" ]]; then
  PASS_RATE="$(python3 - <<'PY'
import json, sys
from pathlib import Path
p = Path("eval/reports/logical_latest.json")
d = json.loads(p.read_text())
rate = d.get("pass_rate") or d.get("pass_pct")
if rate is None and "passed" in d and "total" in d:
    rate = d["passed"] / d["total"] if d["total"] else 0
if rate is None:
    print("0", end="")
elif rate > 1:
    print(rate / 100, end="")
else:
    print(rate, end="")
PY
)"
  echo "Logical pass rate: $PASS_RATE (target ≥ $MIN_PASS)"
  python3 -c "import sys; sys.exit(0 if float('${PASS_RATE}') >= float('${MIN_PASS}') else 1)" || {
    echo "FAIL: logical pass rate below ${MIN_PASS}" >&2
    exit 1
  }
else
  echo "WARN: $REPORT not found"
  [[ "$LOGICAL_RC" -eq 0 ]] || exit "$LOGICAL_RC"
fi

make eval-native || true
make eval-latency || true

echo "Air-gap eval gate passed"

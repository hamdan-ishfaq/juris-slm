#!/usr/bin/env bash
# Phase 9G — collect redacted compliance evidence bundle
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
OUT_DIR="$ROOT/dist/compliance_evidence"
STAMP="$(date +%Y%m%d_%H%M%S)"

mkdir -p "$OUT_DIR" "$ROOT/dist"
echo "== JurisGuard compliance evidence ==" > "$OUT_DIR/README.txt"
echo "Generated: $(date -Iseconds)" >> "$OUT_DIR/README.txt"

# Test summary (non-failing excerpt)
if [[ -x "$ROOT/.venv/bin/pytest" ]]; then
  "$ROOT/.venv/bin/pytest" "$ROOT/backend/tests/test_audit_worm_integration.py" \
    "$ROOT/backend/tests/test_org_isolation_matters.py" \
    -q --tb=no 2>&1 | tail -5 > "$OUT_DIR/test_sample.txt" || true
fi

# Redacted env keys (names only)
if [[ -f "$ROOT/.env" ]]; then
  grep -E '^[A-Z_]+=' "$ROOT/.env" | cut -d= -f1 | sort > "$OUT_DIR/env_keys.txt" || true
fi

# Copy compliance docs
cp "$ROOT/docs/compliance/CONTROL_MATRIX.md" "$OUT_DIR/" 2>/dev/null || true
cp "$ROOT/SECURITY.md" "$OUT_DIR/" 2>/dev/null || true
cp "$ROOT/docs/DISASTER_RECOVERY.md" "$OUT_DIR/" 2>/dev/null || true

# Audit verify (if API up)
API="${COMPLIANCE_API_URL:-http://localhost:8002}"
if curl -sf "$API/health" >/dev/null 2>&1 && [[ -n "${COMPLIANCE_ADMIN_TOKEN:-}" ]]; then
  curl -sf -H "Authorization: Bearer $COMPLIANCE_ADMIN_TOKEN" \
    "$API/api/v1/audit/verify" > "$OUT_DIR/audit_verify_sample.json" || true
fi

mkdir -p "$ROOT/dist"
ARCHIVE="$ROOT/dist/compliance_evidence_${STAMP}.tar.gz"
if command -v zip >/dev/null 2>&1; then
  ARCHIVE="$ROOT/dist/compliance_evidence_${STAMP}.zip"
  (cd "$OUT_DIR" && zip -qr "$ARCHIVE" .)
else
  tar -czf "$ARCHIVE" -C "$OUT_DIR" .
fi
echo "Wrote $ARCHIVE"

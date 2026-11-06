#!/usr/bin/env bash
# Verify Phase 2.2 (auth), 2.3 (corpus), 3 (RAG chat)
set -euo pipefail
cd "$(dirname "$0")/.."
API="${API:-http://localhost:8002}"
EMAIL="${EMAIL:-dev@example.com}"
PASS="${PASS:-jurisdev123}"

echo "=== Phase 2.2 Auth ==="
REG=$(curl -sf -X POST "$API/api/v1/auth/register" \
  -H "Content-Type: application/json" \
  -d "{\"email\":\"$EMAIL\",\"password\":\"$PASS\"}" 2>/dev/null || true)
if [[ -z "$REG" ]]; then
  REG=$(curl -sf -X POST "$API/api/v1/auth/login" \
    -H "Content-Type: application/json" \
    -d "{\"email\":\"$EMAIL\",\"password\":\"$PASS\"}")
fi
TOKEN=$(echo "$REG" | python3 -c "import sys,json; print(json.load(sys.stdin)['access_token'])")
echo "  [OK] token received"

echo "=== Phase 2.3 Corpus stats ==="
curl -sf "$API/api/v1/corpus/stats" | python3 -m json.tool

echo "=== Phase 3 Chat (requires law corpus ingested) ==="
curl -sf -X POST "$API/api/v1/chat" \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"message":"What is the purpose of data processing under GDPR?","use_law_corpus":true}' \
  | python3 -m json.tool | head -40

echo ""
echo "Phase 2.2-3 verify done."

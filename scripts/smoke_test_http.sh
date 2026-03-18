#!/usr/bin/env bash
set -euo pipefail

BASE_URL="http://localhost:8001"
RAND_EMAIL="smoke_$(date +%s)@test.local"
RAND_PASS="TestPass123!"

echo "============================================"
echo "HTTP Smoke Test (No Browser Required)"
echo "Target: $BASE_URL"
echo "============================================"

# Health check
echo "[1/4] Health check..."
HTTP_CODE=$(curl -s -o /dev/null -w "%{http_code}" "$BASE_URL/health" || echo "000")
if [ "$HTTP_CODE" != "200" ]; then
  echo "[FAIL] Backend not responding (HTTP $HTTP_CODE)"
  exit 1
fi
echo "✅ Backend healthy"

# Register
echo "[2/4] User registration..."
REGISTER_RESP=$(curl -s -w "\n%{http_code}" -X POST "$BASE_URL/auth/register" \
  -H "Content-Type: application/json" \
  -d "{\"email\":\"$RAND_EMAIL\",\"password\":\"$RAND_PASS\",\"full_name\":\"Smoke Test\"}")
REGISTER_CODE=$(echo "$REGISTER_RESP" | tail -n1)
if [ "$REGISTER_CODE" != "201" ]; then
  echo "[FAIL] Registration failed (HTTP $REGISTER_CODE)"
  exit 1
fi
echo "✅ Registration successful"

# Login
echo "[3/4] Authentication..."
LOGIN_RESP=$(curl -s -X POST "$BASE_URL/auth/token" \
  -H "Content-Type: application/x-www-form-urlencoded" \
  -d "username=$RAND_EMAIL&password=$RAND_PASS")
TOKEN=$(echo "$LOGIN_RESP" | grep -o '"access_token":"[^"]*"' | cut -d'"' -f4 || echo "")
if [ -z "$TOKEN" ]; then
  echo "[FAIL] Login failed (no token)"
  exit 1
fi
echo "✅ Login successful"

# Chat query
echo "[4/4] Chat endpoint..."
CHAT_RESP=$(curl -s -w "\n%{http_code}" -X POST "$BASE_URL/chat/query" \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"query":"test"}')
CHAT_CODE=$(echo "$CHAT_RESP" | tail -n1)
if [ "$CHAT_CODE" != "200" ]; then
  echo "[FAIL] Chat query failed (HTTP $CHAT_CODE)"
  exit 1
fi
echo "✅ Chat query successful"

echo "============================================"
echo "SYSTEM HEALTHY ✅"
echo "All HTTP endpoints validated"
echo "============================================"

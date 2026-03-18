#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
FRONTEND_DIR="${ROOT_DIR}/frontend"

echo "============================================"
echo "BEWEIS E2E Verification"
echo "Target: http://localhost:8001"
echo "============================================"

if ! command -v npm >/dev/null 2>&1; then
  echo "[FAIL] npm is required"
  exit 1
fi

echo "[INFO] Installing frontend dependencies (if needed)..."
cd "${FRONTEND_DIR}"
npm install

echo "[INFO] Installing Playwright Chromium browser..."
npx playwright install chromium

echo "[INFO] Running E2E smoke tests in headless mode..."
npm run e2e

echo "============================================"
echo "SYSTEM HEALTHY ✅"
echo "E2E smoke verification passed"
echo "============================================"
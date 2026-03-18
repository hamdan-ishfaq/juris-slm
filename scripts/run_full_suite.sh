#!/usr/bin/env bash
set -u

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
BACKEND_STATUS=0
FRONTEND_STATUS=0

echo "============================================"
echo "BEWEIS Full Test Suite"
echo "Root: ${ROOT_DIR}"
echo "============================================"

if ! command -v docker >/dev/null 2>&1; then
  echo "[FAIL] Docker is not installed or not on PATH"
  exit 1
fi

if ! command -v docker-compose >/dev/null 2>&1 && ! docker compose version >/dev/null 2>&1; then
  echo "[FAIL] Neither docker-compose nor docker compose is available"
  exit 1
fi

if docker compose version >/dev/null 2>&1; then
  COMPOSE_CMD="docker compose"
else
  COMPOSE_CMD="docker-compose"
fi

echo "[INFO] Checking Docker daemon..."
if ! docker info >/dev/null 2>&1; then
  echo "[FAIL] Docker daemon is not running"
  exit 1
fi

echo "[INFO] Running backend tests inside container..."
if ! (cd "${ROOT_DIR}" && ${COMPOSE_CMD} ps backend >/dev/null 2>&1); then
  echo "[FAIL] Backend service is not available in compose"
  BACKEND_STATUS=1
else
  (cd "${ROOT_DIR}" && ${COMPOSE_CMD} exec backend pytest -v tests) || BACKEND_STATUS=$?
fi

echo "[INFO] Running frontend tests locally..."
if [ ! -d "${ROOT_DIR}/frontend/node_modules" ]; then
  echo "[INFO] Installing frontend dependencies..."
  (cd "${ROOT_DIR}/frontend" && npm install) || FRONTEND_STATUS=$?
fi

if [ ${FRONTEND_STATUS} -eq 0 ]; then
  (cd "${ROOT_DIR}/frontend" && npm test) || FRONTEND_STATUS=$?
fi

echo "============================================"
echo "Test Report"
if [ ${BACKEND_STATUS} -eq 0 ]; then
  echo "Backend: PASS"
else
  echo "Backend: FAIL (${BACKEND_STATUS})"
fi

if [ ${FRONTEND_STATUS} -eq 0 ]; then
  echo "Frontend: PASS"
else
  echo "Frontend: FAIL (${FRONTEND_STATUS})"
fi

if [ ${BACKEND_STATUS} -eq 0 ] && [ ${FRONTEND_STATUS} -eq 0 ]; then
  echo "Overall: PASS"
  exit 0
fi

echo "Overall: FAIL"
exit 1
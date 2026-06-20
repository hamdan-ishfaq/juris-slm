#!/usr/bin/env bash
# Start Vite for WSL2 + Windows browser access.
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
WSL_IP="$(hostname -I | awk '{print $1}')"

echo ""
echo "=== JurisGuard UI (Vite) ==="
echo "  From WSL:     http://127.0.0.1:5173"
echo "  From Windows: http://localhost:5173"
echo "                http://127.0.0.1:5173"
if [[ -n "${WSL_IP}" ]]; then
  echo "  WSL IP (use if localhost fails): http://${WSL_IP}:5173"
fi
echo ""
echo "API proxy → http://127.0.0.1:8002 (ensure: cd v2 && docker compose up -d api)"
echo "Press Ctrl+C to stop."
echo ""

cd "${ROOT}/frontend"
npm install
exec npm run dev

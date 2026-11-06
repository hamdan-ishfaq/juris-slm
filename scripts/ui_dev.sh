#!/usr/bin/env bash
# Start Vite for WSL2 + Windows browser access.
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
PORT="${VITE_PORT:-5173}"
WSL_IP="$(hostname -I | awk '{print $1}')"
MODE="${1:-}"

print_urls() {
  echo ""
  echo "=== JurisGuard UI (Vite) ==="
  echo "  From WSL:     http://127.0.0.1:${PORT}"
  echo "  From Windows: http://localhost:${PORT}"
  echo "                http://127.0.0.1:${PORT}"
  if [[ -n "${WSL_IP}" ]]; then
    echo "  WSL IP (use if localhost fails): http://${WSL_IP}:${PORT}"
  fi
  echo ""
  echo "API proxy → http://127.0.0.1:8002 (ensure: cd v2 && docker compose up -d api)"
}

port_pids() {
  if command -v lsof >/dev/null 2>&1; then
    lsof -ti ":${PORT}" 2>/dev/null || true
  elif command -v fuser >/dev/null 2>&1; then
    fuser -n tcp "${PORT}" 2>/dev/null | tr -s ' ' '\n' | grep -E '^[0-9]+$' || true
  else
    ss -tlnp 2>/dev/null | awk -v p=":${PORT}" '$4 ~ p { print $NF }' | grep -oP 'pid=\K[0-9]+' || true
  fi
}

is_our_vite() {
  local pid="$1"
  local args
  args=$(ps -p "$pid" -o args= 2>/dev/null || echo "")
  [[ "$args" == *vite* ]] && [[ "$args" == *"${ROOT}/frontend"* || "$args" == *"jurisguard-v2-ui"* ]]
}

stop_port_vite() {
  local pids pid
  pids=$(port_pids)
  [[ -z "$pids" ]] && return 0
  for pid in $pids; do
    if is_our_vite "$pid"; then
      echo "Stopping Vite on :${PORT} (pid ${pid})..."
      kill "$pid" 2>/dev/null || true
      sleep 1
      if kill -0 "$pid" 2>/dev/null; then
        kill -9 "$pid" 2>/dev/null || true
      fi
    else
      local args
      args=$(ps -p "$pid" -o args= 2>/dev/null || echo "unknown")
      echo "ERROR: Port ${PORT} is in use by another process (pid ${pid}):"
      echo "  ${args}"
      echo ""
      echo "Free the port, or start on another port:"
      echo "  VITE_PORT=5174 make ui-dev"
      exit 1
    fi
  done
  sleep 0.5
}

vite_healthy() {
  curl -sf "http://127.0.0.1:${PORT}/" >/dev/null 2>&1
}

if [[ "$MODE" == "--stop" ]]; then
  stop_port_vite
  echo "Stopped UI dev server on :${PORT}."
  exit 0
fi

if [[ "$MODE" == "--restart" ]]; then
  stop_port_vite
elif [[ -n "$(port_pids)" ]]; then
  pid=$(port_pids | head -1)
  if is_our_vite "$pid" && vite_healthy; then
    print_urls
    echo "Already running (pid ${pid}). Open the URL above."
    echo "To restart: make ui-dev-restart"
    echo "Press Ctrl+C does not apply — server is in another terminal."
    exit 0
  fi
  echo "Port ${PORT} busy but not a healthy JurisGuard Vite — restarting..."
  stop_port_vite
fi

print_urls
echo "Press Ctrl+C to stop."
echo ""

cd "${ROOT}/frontend"
npm install
export VITE_PORT="${PORT}"
exec npm run dev

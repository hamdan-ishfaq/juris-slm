#!/usr/bin/env bash
# Air-gap installation wizard — run on target host after extracting bundle.
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"

echo "=== JurisGuard V2 Air-Gap Setup ==="

need_cmd() {
  command -v "$1" >/dev/null 2>&1 || { echo "ERROR: $1 required" >&2; exit 1; }
}
need_cmd docker
docker compose version >/dev/null 2>&1 || { echo "ERROR: docker compose v2 required" >&2; exit 1; }

if command -v nvidia-smi >/dev/null 2>&1; then
  echo "GPU detected — use native Ollama with GPU for best latency (see scripts/setup_ollama_gpu.sh)"
fi

# Load Docker images if present
if [[ -d images ]]; then
  for img in images/*.tar.gz; do
    [[ -f "$img" ]] || continue
    echo "Loading $img..."
    gunzip -c "$img" | docker load
  done
fi

# Copy models
mkdir -p data/models
if [[ -d models ]]; then
  cp -a models/* data/models/ 2>/dev/null || true
fi

# Copy corpus
if [[ -d corpus/law_corpus ]]; then
  mkdir -p data/raw
  cp -a corpus/law_corpus data/raw/
fi

# Compose files
mkdir -p compose
if [[ -f compose/docker-compose.yml ]]; then
  cp compose/*.yml ./
fi

# Environment
ENV_FILE="${ENV_FILE:-.env}"
if [[ ! -f "$ENV_FILE" ]]; then
  if [[ -f config/.env.airgap.template ]]; then
    cp config/.env.airgap.template "$ENV_FILE"
  elif [[ -f .env.airgap.example ]]; then
    cp .env.airgap.example "$ENV_FILE"
  else
  cat > "$ENV_FILE" <<'ENVEOF'
LLM_PROVIDER=ollama
OLLAMA_BASE_URL=http://host.docker.internal:11434
OLLAMA_MODEL=mistral:7b-instruct-v0.3-q4_K_M
OLLAMA_AUX_MODEL=qwen2.5:3b
AIRGAP_LATENCY_PROFILE=true
ADAPTIVE_HYDE_ENABLED=false
CRAG_RETRY_ENABLED=false
GRAPH_EXTRACTION_ENABLED=false
REGISTRATION_OPEN=false
ENVIRONMENT=production
ENVEOF
  fi
fi

if ! grep -q '^AUTH_SECRET_KEY=.\{20,\}' "$ENV_FILE" 2>/dev/null; then
  secret="$(openssl rand -hex 32 2>/dev/null || python3 -c 'import secrets; print(secrets.token_hex(32))')"
  echo "AUTH_SECRET_KEY=$secret" >> "$ENV_FILE"
  echo "Generated AUTH_SECRET_KEY"
fi

read -rp "Admin email [admin@local]: " ADMIN_EMAIL
ADMIN_EMAIL="${ADMIN_EMAIL:-admin@local}"
read -rsp "Admin password (min 8 chars): " ADMIN_PASSWORD
echo
read -rp "Organization name [Default Organization]: " ORG_NAME
ORG_NAME="${ORG_NAME:-Default Organization}"

export ADMIN_EMAIL ADMIN_PASSWORD ORG_NAME

echo "Starting services..."
docker compose -f docker-compose.yml -f docker-compose.prod.yml up -d --remove-orphans

echo "Waiting for API..."
for i in $(seq 1 30); do
  curl -sf http://localhost:8002/health >/dev/null 2>&1 && break
  sleep 2
done

echo "Running migrations..."
docker compose exec -T api alembic upgrade head

echo "Seeding admin user..."
docker compose exec -T \
  -e ADMIN_EMAIL="$ADMIN_EMAIL" \
  -e ADMIN_PASSWORD="$ADMIN_PASSWORD" \
  -e ORG_NAME="$ORG_NAME" \
  api python /app/scripts/seed_admin.py || \
  ADMIN_EMAIL="$ADMIN_EMAIL" ADMIN_PASSWORD="$ADMIN_PASSWORD" ORG_NAME="$ORG_NAME" \
    DATABASE_URL="${DATABASE_URL:-postgresql+asyncpg://juris:juris_password@localhost:5433/juris_db}" \
    python3 "$ROOT/scripts/seed_admin.py"

echo ""
echo "=== Setup complete ==="
echo "Open: http://localhost:8002/app"
echo "Admin: $ADMIN_EMAIL"
echo "Ensure Ollama is running with:"
echo "  ollama pull mistral:7b-instruct-v0.3-q4_K_M"
echo "  ollama pull qwen2.5:3b"

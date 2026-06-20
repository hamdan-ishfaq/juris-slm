#!/usr/bin/env bash
# Build offline air-gap bundle: Docker images, ML models, corpus, compose, checksums.
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"

BUNDLE_DIR="${BUNDLE_DIR:-$ROOT/data/airgap-bundle}"
STAMP="$(date -u +%Y%m%dT%H%M%SZ)"
OUT="$BUNDLE_DIR/juris-airgap-$STAMP"
mkdir -p "$OUT"/{images,models,corpus,compose,config,scripts}

echo "==> JurisGuard air-gap bundle → $OUT"

# --- ML models (required) ---
MODEL_SRC="$ROOT/data/models"
for model in bge-m3 reranker; do
  if [[ ! -d "$MODEL_SRC/$model" ]]; then
    echo "ERROR: missing $MODEL_SRC/$model — run: make models" >&2
    exit 1
  fi
  echo "Copying model $model..."
  cp -a "$MODEL_SRC/$model" "$OUT/models/"
done

# --- Law corpus (optional but recommended) ---
CORPUS_SRC="$ROOT/data/raw/law_corpus"
if [[ -d "$CORPUS_SRC" ]]; then
  cp -a "$CORPUS_SRC" "$OUT/corpus/law_corpus"
else
  echo "WARN: no law corpus at $CORPUS_SRC — bundle will ship without pre-indexed law text"
  mkdir -p "$OUT/corpus/law_corpus"
fi

# --- Compose + config ---
cp docker-compose.yml docker-compose.prod.yml "$OUT/compose/"
[[ -f docker-compose.gpu.yml ]] && cp docker-compose.gpu.yml "$OUT/compose/"
cp .env.airgap.example "$OUT/config/.env.airgap.template"
cp docs/README-INSTALL.md "$OUT/README-INSTALL.md"
cp scripts/setup.sh scripts/verify_airgap_bundle.sh "$OUT/scripts/"
chmod +x "$OUT/scripts/"*.sh
[[ -f scripts/seed_admin.py ]] && cp scripts/seed_admin.py "$OUT/scripts/"

# --- Docker images ---
echo "Building api + worker images..."
docker compose build api worker
PROJECT="$(basename "$ROOT" | tr '[:upper:]' '[:lower:]' | tr -c 'a-z0-9' '-')"
for svc in api worker; do
  img="$(docker compose images -q "$svc" | head -1)"
  if [[ -z "$img" ]]; then
    img="${PROJECT}-${svc}:latest"
    docker tag "$(docker images -q "${PROJECT}-${svc}" 2>/dev/null | head -1)" "$img" 2>/dev/null || true
  fi
  tag="${PROJECT}-${svc}:airgap"
  docker tag "$img" "$tag" 2>/dev/null || docker tag "$(docker compose images -q "$svc")" "$tag"
  echo "Saving $tag..."
  docker save "$tag" | gzip -9 > "$OUT/images/${svc}.tar.gz"
done

# Pull + save infra images (pgvector, redis)
for pair in "pgvector/pgvector:pg15:pgvector.tar.gz" "redis:7-alpine:redis.tar.gz"; do
  IFS=: read -r image outfile <<< "$pair"
  docker pull "$image"
  docker save "$image" | gzip -9 > "$OUT/images/$outfile"
done

# --- Ollama model manifest (host must import separately) ---
OLLAMA_MODELS="${OLLAMA_MODEL:-mistral:7b-instruct-q4_K_M} ${OLLAMA_AUX_MODEL:-qwen2.5:0.5b}"
cat > "$OUT/MANIFEST.json" <<EOF
{
  "created": "$(date -u +%Y-%m-%dT%H:%M:%SZ)",
  "bundle_version": "10",
  "images": ["images/api.tar.gz", "images/worker.tar.gz", "images/pgvector.tar.gz", "images/redis.tar.gz"],
  "models": ["models/bge-m3", "models/reranker"],
  "corpus": ["corpus/law_corpus"],
  "ollama_models": [$(printf '"%s",' $OLLAMA_MODELS | sed 's/,$//')],
  "compose": ["compose/docker-compose.yml", "compose/docker-compose.prod.yml"],
  "env_profile": "LLM_PROVIDER=ollama",
  "setup": "scripts/setup.sh"
}
EOF

( cd "$OUT" && find . -type f ! -name 'MANIFEST.sha256' -print0 | sort -z | xargs -0 sha256sum ) > "$OUT/MANIFEST.sha256"

ARCHIVE="${BUNDLE_DIR}/juris-airgap-${STAMP}.tar.zst"
if command -v zstd >/dev/null 2>&1; then
  tar -C "$BUNDLE_DIR" -cf - "juris-airgap-$STAMP" | zstd -19 -o "$ARCHIVE"
  echo "Compressed bundle: $ARCHIVE"
else
  ARCHIVE="${BUNDLE_DIR}/juris-airgap-${STAMP}.tar.gz"
  tar -C "$BUNDLE_DIR" -czf "$ARCHIVE" "juris-airgap-$STAMP"
  echo "Compressed bundle (gzip): $ARCHIVE"
fi

echo "Done. Transfer $ARCHIVE to target host and run scripts/setup.sh"

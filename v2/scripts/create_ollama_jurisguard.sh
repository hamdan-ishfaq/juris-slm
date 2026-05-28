#!/usr/bin/env bash
# Create Ollama model from GGUF in your training folder.
# Run from v2/:  bash scripts/create_ollama_jurisguard.sh [model-name]
set -euo pipefail
cd "$(dirname "$0")/.."

MODEL_NAME="${1:-jurisguard-dev}"
GGUF_DIR="${TRAINING_DIR:-/mnt/c/Users/mhamd/Desktop/PROJECT/juris/training}/gguf"

if [[ ! -d "$GGUF_DIR" ]]; then
  echo "GGUF folder not found: $GGUF_DIR" >&2
  echo "Set TRAINING_DIR in .env or pass a path." >&2
  exit 1
fi

GGUF_FILE="$(find "$GGUF_DIR" -maxdepth 2 -type f \( -name '*.gguf' -o -name '*.GGUF' \) | head -1)"
if [[ -z "$GGUF_FILE" ]]; then
  echo "No .gguf file under $GGUF_DIR" >&2
  echo "Contents:" >&2
  ls -la "$GGUF_DIR" >&2 || true
  echo "" >&2
  echo "Finish Colab Cell 8 (export GGUF) or wait until training completes." >&2
  exit 1
fi

GGUF_BASENAME="$(basename "$GGUF_FILE")"
MODEFILE_HOST="$GGUF_DIR/Modelfile.jurisguard"
MODEFILE_IN_CONTAINER="/training/gguf/Modelfile.jurisguard"

cat > "$MODEFILE_HOST" <<EOF
FROM /training/gguf/${GGUF_BASENAME}
PARAMETER temperature 0.1
PARAMETER num_ctx 4096
SYSTEM You are JurisGuard, an expert legal contract analyst. Provide precise, grounded answers citing relevant clauses when possible.
EOF

echo "GGUF: $GGUF_FILE"
echo "Modelfile: $MODEFILE_HOST"
echo "Creating Ollama model: $MODEL_NAME"

docker compose up -d ollama
docker compose exec ollama ollama create "$MODEL_NAME" -f "$MODEFILE_IN_CONTAINER"

echo ""
echo "Done. Add to v2/.env:"
echo "  OLLAMA_MODEL=$MODEL_NAME"
echo "Then: docker compose restart api"

#!/usr/bin/env bash
# Ingest law corpus from WSL host (avoids Docker rebuild when ML stack already works locally)
set -euo pipefail
cd "$(dirname "$0")/.."

export DATABASE_URL="${DATABASE_URL:-postgresql+asyncpg://juris:juris_password@localhost:5433/juris_db}"
export EMBEDDING_MODEL_PATH="${EMBEDDING_MODEL_PATH:-$(pwd)/data/models/bge-m3}"
export RERANKER_MODEL_PATH="${RERANKER_MODEL_PATH:-$(pwd)/data/models/reranker}"
export LAW_CORPUS_PATH="${LAW_CORPUS_PATH:-$(pwd)/data/raw/law_corpus}"

if [[ ! -d "$EMBEDDING_MODEL_PATH" ]]; then
  echo "Missing bge-m3 at $EMBEDDING_MODEL_PATH — run: python scripts/download_assets.py --models --only bge-m3"
  exit 1
fi

source .venv/bin/activate 2>/dev/null || true
pip install -q -r backend/requirements-base.txt 2>/dev/null || true
pip install -q "torch>=2.5.1" --index-url https://download.pytorch.org/whl/cpu 2>/dev/null || true
pip install -q -r backend/requirements-ml.txt

python scripts/run_ingest_law.py

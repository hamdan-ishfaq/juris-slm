#!/usr/bin/env bash
# Phase 10A — install Ollama with GPU offload on WSL2/Linux
set -euo pipefail

echo "== JurisGuard Ollama GPU setup =="

if ! command -v nvidia-smi >/dev/null 2>&1; then
  echo "WARNING: nvidia-smi not found — Ollama will run on CPU only"
else
  nvidia-smi --query-gpu=name,memory.total --format=csv,noheader
fi

if ! command -v ollama >/dev/null 2>&1; then
  curl -fsSL https://ollama.com/install.sh | sh
fi

export OLLAMA_NUM_GPU="${OLLAMA_NUM_GPU:-99}"
echo "OLLAMA_NUM_GPU=$OLLAMA_NUM_GPU"

echo "Pulling air-gap models (this may take several minutes)..."
ollama pull mistral:7b-instruct-q4_K_M || ollama pull mistral:7b-instruct
ollama pull qwen2.5:0.5b

echo ""
echo "Done. Start Ollama: ollama serve"
echo "Docker .env: OLLAMA_BASE_URL=http://host.docker.internal:11434"
echo "             OLLAMA_MODEL=mistral:7b-instruct-q4_K_M"

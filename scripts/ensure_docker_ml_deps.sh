#!/usr/bin/env bash
# Pin ML stack inside running API container (no full image rebuild).
set -euo pipefail
cd "$(dirname "$0")/.."
exec python3 scripts/ensure_docker_ml_deps.py

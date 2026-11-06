#!/usr/bin/env bash
# Phase 0.2 — Verify v2 directory scaffold
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"

REQUIRED_DIRS=(
    "scripts"
    "notebooks"
    "data/raw"
    "data/processed"
    "data/models"
    "data/uploads"
    "data/law_corpus"
    "backend/src"
    "backend/alembic/versions"
    "backend/tests"
    "frontend/src"
)

REQUIRED_FILES=(
    "README.md"
    ".gitignore"
    "scripts/00_verify_gpu.sh"
    "scripts/00_verify_scaffold.sh"
)

pass=0
fail=0

echo "========================================"
echo " Phase 0.2 — Scaffold Verification"
echo "========================================"

for dir in "${REQUIRED_DIRS[@]}"; do
    if [[ -d "$dir" ]]; then
        echo "  [DIR]  $dir — OK"
        pass=$((pass + 1))
    else
        echo "  [DIR]  $dir — MISSING"
        fail=$((fail + 1))
    fi
done

for file in "${REQUIRED_FILES[@]}"; do
    if [[ -f "$file" ]]; then
        echo "  [FILE] $file — OK"
        pass=$((pass + 1))
    else
        echo "  [FILE] $file — MISSING"
        fail=$((fail + 1))
    fi
done

echo
echo " Results: $pass OK, $fail missing"

if [[ "$fail" -eq 0 ]]; then
    echo "Phase 0.2 COMPLETE — scaffold ready"
    exit 0
else
    echo "Phase 0.2 INCOMPLETE"
    exit 1
fi

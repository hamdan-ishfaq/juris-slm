#!/usr/bin/env bash
# Phase 0.3/0.4 — Verify datasets and models are on disk
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
exec python3 "$ROOT/scripts/verify_assets.py"

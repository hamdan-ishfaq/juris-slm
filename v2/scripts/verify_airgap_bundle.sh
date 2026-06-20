#!/usr/bin/env bash
# Verify extracted air-gap bundle integrity.
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"

if [[ ! -f MANIFEST.sha256 ]]; then
  echo "ERROR: MANIFEST.sha256 not found — run from bundle root" >&2
  exit 1
fi

sha256sum -c MANIFEST.sha256
echo "Checksums OK"

for model in models/bge-m3 models/reranker; do
  [[ -d "$model" ]] || { echo "ERROR: missing $model" >&2; exit 1; }
done
echo "Models OK"

for img in images/api.tar.gz images/worker.tar.gz; do
  [[ -f "$img" ]] || echo "WARN: missing $img (build on source host first)"
done

echo "Bundle verification passed"

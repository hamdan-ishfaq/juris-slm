#!/usr/bin/env bash
# Copy Colab upload files to Windows Desktop
set -euo pipefail

SRC_DIR="$(cd "$(dirname "$0")/../data/processed" && pwd)"
DESKTOP="/mnt/c/Users/mhamd/Desktop"

for f in train_final.jsonl eval_set.jsonl; do
  src="$SRC_DIR/$f"
  if [[ ! -f "$src" ]]; then
    echo "MISSING: $src" >&2
    echo "Run Phase 1 first: python scripts/04_build_final_dataset.py" >&2
    exit 1
  fi
done

mkdir -p "$DESKTOP"
cp -v "$SRC_DIR/train_final.jsonl" "$SRC_DIR/eval_set.jsonl" "$DESKTOP/"
ls -lh "$DESKTOP/train_final.jsonl" "$DESKTOP/eval_set.jsonl"
echo ""
echo "Done. Files are on your Windows Desktop:"
echo "  C:\\Users\\mhamd\\Desktop\\train_final.jsonl"
echo "  C:\\Users\\mhamd\\Desktop\\eval_set.jsonl"

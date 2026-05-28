#!/usr/bin/env python3
"""
Phase 1.2 — Merge per-dataset JSONL into train/eval splits for Colab fine-tuning.

Usage:
  python scripts/04_build_final_dataset.py
  python scripts/04_build_final_dataset.py --eval-ratio 0.1

Output:
  data/processed/train_final.jsonl
  data/processed/eval_set.jsonl
  data/processed/dataset_stats.json
"""
from __future__ import annotations

import argparse
import json
import random
import sys
from collections import Counter
from pathlib import Path

from tqdm import tqdm

from training_common import PROCESSED, ensure_processed_dir, write_jsonl

PAIR_FILES = [
    "cuad_pairs.jsonl",
    "contract_nli_pairs.jsonl",
    "ledgar_pairs.jsonl",
    "maud_pairs.jsonl",
    "synthetic_pairs.jsonl",  # optional, included if present
]


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--eval-ratio", type=float, default=0.1, help="Eval split ratio (default 0.1)")
    parser.add_argument("--seed", type=int, default=42)
    args = parser.parse_args()

    ensure_processed_dir()
    all_rows: list[dict] = []

    print("Merging instruction pairs:")
    for name in PAIR_FILES:
        path = PROCESSED / name
        if not path.exists():
            print(f"  [SKIP] {name} (not found)")
            continue
        rows = []
        with path.open(encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if line:
                    rows.append(json.loads(line))
        print(f"  [OK]   {name}: {len(rows):,} examples")
        all_rows.extend(rows)

    if not all_rows:
        print("No pair files found. Run 02_prepare_training_data.py first.", file=sys.stderr)
        return 1

    print(f"\nTotal before dedup: {len(all_rows):,}")

    # Dedup by (instruction, input, output)
    seen: set[tuple[str, str, str]] = set()
    unique: list[dict] = []
    for row in tqdm(all_rows, desc="Dedup", unit="ex"):
        key = (row.get("instruction", ""), row.get("input", ""), row.get("output", ""))
        if key in seen:
            continue
        seen.add(key)
        unique.append(row)

    print(f"Total after dedup:  {len(unique):,}")

    rng = random.Random(args.seed)
    rng.shuffle(unique)

    eval_n = max(1, int(len(unique) * args.eval_ratio))
    eval_rows = unique[:eval_n]
    train_rows = unique[eval_n:]

    train_path = PROCESSED / "train_final.jsonl"
    eval_path = PROCESSED / "eval_set.jsonl"
    stats_path = PROCESSED / "dataset_stats.json"

    write_jsonl(train_path, train_rows)
    write_jsonl(eval_path, eval_rows)

    source_counts = Counter(r.get("source", "unknown") for r in unique)
    stats = {
        "total_unique": len(unique),
        "train": len(train_rows),
        "eval": len(eval_rows),
        "eval_ratio": args.eval_ratio,
        "seed": args.seed,
        "by_source": dict(source_counts),
        "files_merged": [n for n in PAIR_FILES if (PROCESSED / n).exists()],
    }
    stats_path.write_text(json.dumps(stats, indent=2), encoding="utf-8")

    print(f"\n✓ train → {train_path} ({len(train_rows):,} examples)")
    print(f"✓ eval  → {eval_path} ({len(eval_rows):,} examples)")
    print(f"✓ stats → {stats_path}")
    print("\nBy source:", dict(source_counts))
    print("\nPhase 1.2 complete. Upload train_final.jsonl + eval_set.jsonl to Google Drive for Colab.")
    return 0


if __name__ == "__main__":
    sys.exit(main())

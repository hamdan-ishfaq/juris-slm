#!/usr/bin/env python3
"""Verify Phase 1 training data outputs."""
from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PROCESSED = ROOT / "data" / "processed"

REQUIRED_PAIR_FILES = [
    "cuad_pairs.jsonl",
    "contract_nli_pairs.jsonl",
    "ledgar_pairs.jsonl",
    "maud_pairs.jsonl",
]

FINAL_FILES = [
    "train_final.jsonl",
    "eval_set.jsonl",
    "dataset_stats.json",
]


def count_lines(path: Path) -> int:
    if not path.exists():
        return 0
    with path.open(encoding="utf-8") as f:
        return sum(1 for line in f if line.strip())


def main() -> int:
    ok = 0
    fail = 0

    print("=" * 40)
    print(" Phase 1.1 — Per-dataset pairs")
    print("=" * 40)
    for name in REQUIRED_PAIR_FILES:
        path = PROCESSED / name
        n = count_lines(path)
        if n > 0:
            print(f"  [OK]   {name} ({n:,} lines)")
            ok += 1
        else:
            print(f"  [MISS] {name}")
            fail += 1

    synth = PROCESSED / "synthetic_pairs.jsonl"
    n = count_lines(synth)
    if n > 0:
        print(f"  [OK]   synthetic_pairs.jsonl ({n:,} lines) [optional]")
    else:
        print("  [SKIP] synthetic_pairs.jsonl (optional — needs Ollama)")

    print()
    print("=" * 40)
    print(" Phase 1.2 — Final splits")
    print("=" * 40)
    for name in FINAL_FILES:
        path = PROCESSED / name
        if name.endswith(".jsonl"):
            n = count_lines(path)
            if n > 0:
                print(f"  [OK]   {name} ({n:,} lines)")
                ok += 1
            else:
                print(f"  [MISS] {name}")
                fail += 1
        elif path.exists() and path.stat().st_size > 10:
            print(f"  [OK]   {name}")
            ok += 1
        else:
            print(f"  [MISS] {name}")
            fail += 1

    stats_path = PROCESSED / "dataset_stats.json"
    if stats_path.exists():
        stats = json.loads(stats_path.read_text(encoding="utf-8"))
        print()
        print(" Stats:", json.dumps(stats.get("by_source", {}), indent=2))

    print()
    print(f" Results: {ok} OK, {fail} missing")
    if fail == 0:
        print(" Phase 1 COMPLETE")
        return 0
    print(" Run the Phase 1 commands in README order.")
    return 1


if __name__ == "__main__":
    sys.exit(main())

#!/usr/bin/env python3
"""Compare two law corpus snapshots for regulatory change alerts."""
from __future__ import annotations

import argparse
import hashlib
from pathlib import Path

V2_ROOT = Path(__file__).resolve().parents[1]
CORPUS = V2_ROOT / "data" / "raw" / "law_corpus"


def file_hash(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()[:16]


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--dir", type=Path, default=CORPUS)
    args = parser.parse_args()
    if not args.dir.is_dir():
        print(f"No corpus at {args.dir}")
        return 1
    for p in sorted(args.dir.glob("*.txt")):
        print(f"{p.name}\t{file_hash(p)}\t{p.stat().st_size} bytes")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

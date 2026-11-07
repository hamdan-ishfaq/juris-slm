#!/usr/bin/env python3
"""Score the injection guard on deepset/prompt-injections, pinned, with the product's own check.

  injection.py --output report.json

Label 1 is an injection. Blocking a benign question is a false positive. The dataset is small (662 rows, English and German), so
results carry wide intervals. Tune only on the train split, and score test once.
"""
from __future__ import annotations

import argparse
import io
import json
import random
import sys
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "backend" / "src"))

REVISION = "4f61ecb038e9c3fb77e21034b22511b523772cdd"
BASE = f"https://huggingface.co/datasets/deepset/prompt-injections/resolve/{REVISION}/data"
FILES = {
    "train": "train-00000-of-00001-9564e8b05b4757ab.parquet",
    "test": "test-00000-of-00001-701d16158af87368.parquet",
}
CACHE = ROOT / "data" / "benchmarks" / "prompt_injections"


def load(split: str) -> list[dict]:
    import pyarrow.parquet as pq

    path = CACHE / FILES[split]
    if not path.exists():
        CACHE.mkdir(parents=True, exist_ok=True)
        with urllib.request.urlopen(f"{BASE}/{FILES[split]}", timeout=120) as response:
            path.write_bytes(response.read())
    return pq.read_table(io.BytesIO(path.read_bytes())).to_pylist()


def blocked(text: str) -> bool:
    from fastapi import HTTPException

    from services.rag import _guard_query

    try:
        _guard_query(text)
    except HTTPException:
        return True
    return False


def _interval(hits: list[int], rounds: int = 1000) -> list[float]:
    if not hits:
        return [0.0, 0.0]
    rng = random.Random(7)
    means = sorted(sum(rng.choices(hits, k=len(hits))) / len(hits) for _ in range(rounds))
    return [round(means[25], 3), round(means[974], 3)]


def score(rows: list[dict]) -> dict:
    from services.rag import looks_german

    out = {}
    groups = {"all": rows, "german": [r for r in rows if looks_german(r["text"])]}
    groups["english"] = [r for r in rows if r not in groups["german"]]
    for name, group in groups.items():
        flags = [(r["label"], blocked(r["text"])) for r in group]
        attacks = [b for label, b in flags if label == 1]
        benign = [b for label, b in flags if label == 0]
        tp, fp = sum(attacks), sum(benign)
        out[name] = {
            "rows": len(group),
            "attacks": len(attacks),
            "recall": round(tp / len(attacks), 3) if attacks else None,
            "recall_ci95": _interval([int(b) for b in attacks]),
            "false_positive_rate": round(fp / len(benign), 3) if benign else None,
            "precision": round(tp / (tp + fp), 3) if tp + fp else None,
        }
    return out


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", required=True)
    parser.add_argument("--splits", default="train,test")
    args = parser.parse_args()
    report = {"dataset": "deepset/prompt-injections", "revision": REVISION, "guard": "services.rag._guard_query", "splits": {}}
    for split in args.splits.split(","):
        report["splits"][split] = score(load(split))
    Path(args.output).parent.mkdir(parents=True, exist_ok=True)
    Path(args.output).write_text(json.dumps(report, indent=1) + "\n")
    for split, groups in report["splits"].items():
        for name, m in groups.items():
            print(f"{split:5s} {name:7s} rows {m['rows']:3d} attacks {m['attacks']:3d}  recall {m['recall']} {m['recall_ci95']}  "
                  f"false positives {m['false_positive_rate']}  precision {m['precision']}")
    return 0


if __name__ == "__main__":
    sys.exit(main())

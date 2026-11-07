#!/usr/bin/env python3
"""Score the injection guard on deepset/prompt-injections, pinned, with the product's own check.

  injection.py --output report.json
  injection.py --output report.json --splits "" --own-questions    (false alarms on the project's own questions only)

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
    """Rows as dicts. A JSON copy is kept so the API image, which has no pyarrow, can read them."""
    copy = CACHE / f"{split}.jsonl"
    if copy.exists():
        return [json.loads(line) for line in copy.read_text().splitlines()]
    import pyarrow.parquet as pq

    path = CACHE / FILES[split]
    if not path.exists():
        CACHE.mkdir(parents=True, exist_ok=True)
        with urllib.request.urlopen(f"{BASE}/{FILES[split]}", timeout=120) as response:
            path.write_bytes(response.read())
    rows = pq.read_table(io.BytesIO(path.read_bytes())).to_pylist()
    copy.write_text("".join(json.dumps(row, ensure_ascii=False) + "\n" for row in rows))
    return rows


def _product_guard(text: str) -> bool:
    from fastapi import HTTPException

    from services.rag import _guard_query

    try:
        _guard_query(text)
    except HTTPException:
        return True
    return False


def _classifier_guard():
    """protectai/deberta-v3-base-prompt-injection-v2 on the CPU. Its card says English only."""
    from transformers import pipeline

    classify = pipeline("text-classification", model=str(ROOT / "data" / "models" / "prompt-injection"),
                        device=-1, truncation=True, max_length=512)
    return lambda text: classify(text)[0]["label"] == "INJECTION"


GUARDS = {"product": lambda: _product_guard, "protectai": _classifier_guard}
blocked = _product_guard


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


def own_questions() -> dict:
    """How many of the project's own questions the guard would block. These were written for the project, so the counts only
    show over-blocking on this product's traffic; they are not a benchmark result."""
    golden = ROOT / "eval" / "golden"
    sets = {"law": ("law_qa.jsonl", "question"), "contract": ("contract_qa.jsonl", "question"),
            "benign_lookalikes": ("injection_benign.jsonl", "prompt")}
    out = {}
    for name, (file, field) in sets.items():
        questions = [json.loads(line)[field] for line in (golden / file).read_text().splitlines() if line.strip()]
        flagged = [q for q in questions if blocked(q)]
        out[name] = {"questions": len(questions), "blocked": len(flagged), "blocked_questions": flagged}
    return out


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", required=True)
    parser.add_argument("--splits", default="train,test")
    parser.add_argument("--guard", choices=sorted(GUARDS), default="product")
    parser.add_argument("--own-questions", action="store_true", help="also count blocks on the project's own questions")
    args = parser.parse_args()
    global blocked
    blocked = GUARDS[args.guard]()
    report = {"dataset": "deepset/prompt-injections", "revision": REVISION, "guard": args.guard, "splits": {}}
    for split in filter(None, args.splits.split(",")):
        report["splits"][split] = score(load(split))
    if args.own_questions:
        report["own_questions"] = own_questions()
    Path(args.output).parent.mkdir(parents=True, exist_ok=True)
    Path(args.output).write_text(json.dumps(report, indent=1) + "\n")
    for split, groups in report["splits"].items():
        for name, m in groups.items():
            print(f"{split:5s} {name:7s} rows {m['rows']:3d} attacks {m['attacks']:3d}  recall {m['recall']} {m['recall_ci95']}  "
                  f"false positives {m['false_positive_rate']}  precision {m['precision']}")
    for name, m in report.get("own_questions", {}).items():
        print(f"own {name:17s} blocked {m['blocked']} of {m['questions']}  {m['blocked_questions']}")
    return 0


if __name__ == "__main__":
    sys.exit(main())

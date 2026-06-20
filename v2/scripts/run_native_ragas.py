#!/usr/bin/env python3
"""Native RAGAS evaluation when ragas + judge LLM are installed."""
from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from eval_common import (  # noqa: E402
    GOLDEN_DIR,
    SKIP_LLM,
    api_reachable,
    chat,
    get_eval_user,
    load_baseline,
    load_jsonl,
    save_report,
)


def main() -> int:
    parser = argparse.ArgumentParser(description="Native RAGAS eval (requires ragas package)")
    parser.add_argument("--limit", type=int, default=15)
    parser.add_argument("--report", default="eval/reports/ragas_native_latest.json")
    args = parser.parse_args()

    if SKIP_LLM:
        print("CI_SKIP_LLM=1 — skipping native RAGAS")
        return 0

    try:
        from datasets import Dataset  # type: ignore
        from ragas import evaluate  # type: ignore
        from ragas.metrics import answer_relevancy, faithfulness  # type: ignore
    except ImportError:
        print("Install: pip install ragas datasets")
        return 0

    if not api_reachable():
        print("API not reachable")
        return 1

    cases = load_jsonl(GOLDEN_DIR / "law_qa.jsonl")[: args.limit]
    eval_user = get_eval_user()
    rows: list[dict] = []

    for case in cases:
        q = case["question"]
        r = chat(eval_user["token"], q, timeout=180.0, use_hyde=True)
        resp = r.json() if r.status_code == 200 else {}
        rows.append(
            {
                "question": q,
                "answer": resp.get("answer", ""),
                "contexts": [s.get("content", s.get("label", "")) for s in resp.get("sources", [])],
            }
        )

    ds = Dataset.from_list(rows)
    result = evaluate(ds, metrics=[faithfulness, answer_relevancy])
    metrics = {k: float(v) for k, v in result.items() if isinstance(v, (int, float))}

    report = {
        "suite": "ragas_native",
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "subset_size": len(cases),
        "metrics": metrics,
    }
    save_report(Path(__file__).resolve().parents[1] / args.report, report)

    baseline = load_baseline()
    min_faith = baseline.get("ragas", {}).get("metrics", {}).get("faithfulness", 0.65)
    faith = metrics.get("faithfulness", 0.0)
    print(f"faithfulness={faith:.3f} (baseline floor {min_faith})")
    if faith < min_faith - 0.05:
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())

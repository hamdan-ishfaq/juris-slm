#!/usr/bin/env python3
"""Gold-phrase proxy on a subset of the law questions, against the live API.

This is not RAGAS and measures no faithfulness or relevancy. It only reports whether the gold phrases
appear in the retrieved text and in the answer. Native RAGAS is in run_native_ragas.py.
"""
from __future__ import annotations

import argparse
import os
import sys
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from eval_common import (  # noqa: E402
    GOLDEN_DIR,
    SKIP_LLM,
    api_reachable,
    chat_timeout,
    eval_chat_pipeline,
    forbidden_violation,
    get_eval_user,
    load_baseline,
    load_jsonl,
    save_report,
)


def compute_proxy_metrics(cases: list[dict], token: str) -> dict:
    retrieval_hits = answer_hits = forbidden = http_failed = 0
    scored = [case for case in cases if not case.get("expect_refusal")]
    for case in scored:
        result = eval_chat_pipeline(token, case["question"], case.get("gold_chunk_substrings") or [])
        if not result["http_ok"]:
            http_failed += 1
            continue
        retrieval_hits += result["retrieval_hit"]
        answer_hits += result["answer_hit"]
        forbidden += forbidden_violation(result["answer"], case.get("forbidden_in_answer") or [])
    evaluated = len(scored) - http_failed
    denominator = max(evaluated, 1)
    return {
        "context_gold_recall_proxy": retrieval_hits / denominator,
        "answer_gold_recall_proxy": answer_hits / denominator,
        "forbidden_violation_rate": forbidden / denominator,
        "cases_evaluated": evaluated,
        "cases_http_failed": http_failed,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--subset", type=int, default=15, help="Number of law_qa cases (0=all)")
    parser.add_argument("--no-baseline-gate", action="store_true")
    parser.add_argument("--report", type=Path, default=Path("eval/reports/context_proxy_latest.json"))
    parser.add_argument("--timeout", type=float, default=None, help="Overrides EVAL_CHAT_TIMEOUT")
    args = parser.parse_args()

    if SKIP_LLM:
        print("CI_SKIP_LLM set, skipping the proxy eval")
        return 0
    if not api_reachable():
        print("API not reachable")
        return 1
    if args.timeout is not None:
        os.environ["EVAL_CHAT_TIMEOUT"] = str(args.timeout)

    cases = load_jsonl(GOLDEN_DIR / "law_qa.jsonl")
    if args.subset > 0:
        cases = cases[: args.subset]
    metrics = compute_proxy_metrics(cases, get_eval_user()["token"])
    save_report(
        Path(__file__).resolve().parents[1] / args.report,
        {
            "suite": "context_proxy",
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "metrics": metrics,
            "llm_provider": os.environ.get("LLM_PROVIDER", "openrouter"),
            "ollama_model": os.environ.get("OLLAMA_MODEL", ""),
            "timeout_seconds": chat_timeout(),
        },
    )
    for key, value in metrics.items():
        print(f"  {key}: {value:.3f}" if isinstance(value, float) else f"  {key}: {value}")

    floor = load_baseline().get("context_proxy", {}).get("context_gold_recall_proxy_min", 0.0)
    if not args.no_baseline_gate and metrics["context_gold_recall_proxy"] < floor:
        print(f"FAIL: context_gold_recall_proxy below floor {floor}")
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())

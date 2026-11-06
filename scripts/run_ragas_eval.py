#!/usr/bin/env python3
"""Phase 3 RAGAS / semantic proxy evaluation against live API."""
from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from eval_common import (  # noqa: E402
    BASELINE_PATH,
    GOLDEN_DIR,
    SKIP_LLM,
    api_reachable,
    chat,
    chat_timeout,
    compare_metric,
    forbidden_violation,
    get_eval_user,
    is_ollama_eval,
    is_refusal,
    load_baseline,
    load_jsonl,
    register_user,
    save_report,
    substring_hit,
)


def compute_proxy_metrics(cases: list[dict], token: str, *, timeout: float) -> dict:
    substring_hits = 0
    answer_relevant = 0
    faithfulness_ok = 0
    refusals_ok = 0
    ref_total = 0
    ref_failed = 0
    forbidden_count = 0
    evaluated = 0
    http_failed = 0

    for case in cases:
        if case.get("expect_refusal"):
            ref_total += 1
            r = chat(token, case["question"], timeout=timeout, use_hyde=True)
            if r.status_code == 200 and is_refusal(r.json().get("answer", "")):
                refusals_ok += 1
            elif r.status_code != 200:
                ref_failed += 1
            continue

        r = chat(token, case["question"], timeout=timeout, use_hyde=True)
        if r.status_code != 200:
            http_failed += 1
            continue
        evaluated += 1
        data = r.json()
        answer = data.get("answer", "")
        sources = data.get("sources") or []
        source_blob = answer + " " + json.dumps(sources)

        subs = case.get("gold_chunk_substrings") or []
        if substring_hit(source_blob, subs):
            substring_hits += 1
        if len(answer.strip()) > 30:
            answer_relevant += 1
        if sources and substring_hit(json.dumps(sources), subs):
            faithfulness_ok += 1
        elif substring_hit(answer, subs):
            faithfulness_ok += 1
        if forbidden_violation(answer, case.get("forbidden_in_answer") or []):
            forbidden_count += 1

    n = max(evaluated, 1)
    non_refusal = sum(1 for c in cases if not c.get("expect_refusal"))
    return {
        "context_precision": substring_hits / n,
        "context_recall": substring_hits / n,
        "faithfulness": faithfulness_ok / n,
        "answer_relevancy": answer_relevant / n,
        "refusal_correct_rate": refusals_ok / ref_total if ref_total else 1.0,
        "forbidden_violation_rate": forbidden_count / n,
        "cases_evaluated": evaluated,
        "cases_total": len(cases),
        "cases_non_refusal": non_refusal,
        "cases_http_failed": http_failed,
        "refusal_cases": ref_total,
        "refusal_http_failed": ref_failed,
        "coverage_rate": evaluated / non_refusal if non_refusal else 1.0,
        "complete": http_failed == 0 and ref_failed == 0,
        "mode": "proxy",
        "pipeline": {
            "focus": "15-case retrieval proxy (substring in sources or answer)",
            "note": "Not native RAGAS — gold-phrase recall on returned context",
            "context_gold_recall_proxy": substring_hits / n,
            "source_or_answer_gold_hit_rate": faithfulness_ok / n,
            "cases_evaluated": evaluated,
            "cases_http_failed": http_failed,
        },
    }


def try_ragas_metrics(cases: list[dict], token: str, *, timeout: float) -> dict | None:
    try:
        from datasets import Dataset
        from ragas import evaluate
        from ragas.metrics import answer_relevancy, context_precision, context_recall, faithfulness
    except ImportError:
        return None

    questions, answers, contexts, grounds = [], [], [], []
    for case in cases:
        if case.get("expect_refusal"):
            continue
        r = chat(token, case["question"], timeout=timeout, use_hyde=True)
        if r.status_code != 200:
            continue
        data = r.json()
        answer = data.get("answer", "")
        sources = data.get("sources") or []
        ctx = [json.dumps(s) for s in sources] if sources else [""]
        questions.append(case["question"])
        answers.append(answer)
        contexts.append(ctx)
        grounds.append(" ".join(case.get("gold_chunk_substrings") or case.get("gold_articles") or []))

    if len(questions) < 3:
        return None

    ds = Dataset.from_dict(
        {"question": questions, "answer": answers, "contexts": contexts, "ground_truth": grounds}
    )
    try:
        result = evaluate(ds, metrics=[faithfulness, answer_relevancy, context_precision, context_recall])
        scores = {k: float(v) for k, v in result.items()}
        scores["mode"] = "ragas"
        scores["cases_evaluated"] = len(questions)
        return scores
    except Exception as exc:
        print(f"RAGAS evaluate failed ({exc}); using proxy metrics")
        return None


def main() -> int:
    parser = argparse.ArgumentParser(description="JurisGuard RAGAS / semantic eval")
    parser.add_argument("--subset", type=int, default=15, help="Number of law_qa cases (0=all)")
    parser.add_argument("--compare-baseline", action="store_true")
    parser.add_argument("--no-baseline-gate", action="store_true")
    parser.add_argument("--use-ragas", action="store_true", help="Attempt native RAGAS if installed")
    parser.add_argument("--report", type=Path, default=Path("eval/reports/ragas_latest.json"))
    parser.add_argument("--timeout", type=float, default=None)
    args = parser.parse_args()
    timeout = args.timeout if args.timeout is not None else chat_timeout()

    if SKIP_LLM:
        print("CI_SKIP_LLM set — skipping RAGAS eval")
        return 0

    if not api_reachable():
        print("API not reachable")
        return 1

    cases = load_jsonl(GOLDEN_DIR / "law_qa.jsonl")
    if args.subset > 0:
        cases = cases[: args.subset]

    user = get_eval_user()
    if user.get("dev_master"):
        print(f"Using dev master: {user['email']}")
    metrics = None
    if args.use_ragas:
        metrics = try_ragas_metrics(cases, user["token"], timeout=timeout)
    if metrics is None:
        metrics = compute_proxy_metrics(cases, user["token"], timeout=timeout)

    report = {
        "suite": "ragas",
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "metrics": metrics,
        "subset_size": len(cases),
        "llm_provider": __import__("os").environ.get("LLM_PROVIDER", "openrouter"),
        "ollama_model": __import__("os").environ.get("OLLAMA_MODEL", ""),
    }
    out = Path(__file__).resolve().parents[1] / args.report
    save_report(out, report)

    print("\n=== Semantic Eval Metrics ===")
    for k, v in metrics.items():
        if isinstance(v, float):
            print(f"  {k}: {v:.3f}")

    if args.compare_baseline and not args.no_baseline_gate and not is_ollama_eval():
        baseline = load_baseline()
        ragas_base = baseline.get("ragas", {}).get("metrics", {})
        faith_base = ragas_base.get("faithfulness", 0.0)
        faith_now = metrics.get("faithfulness", 0.0)
        if faith_base > 0 and not compare_metric(faith_now, faith_base, max_drop=0.05):
            print(f"FAIL: faithfulness dropped from {faith_base:.3f} to {faith_now:.3f}")
            return 1
        print("Baseline comparison: OK")

    # Optional native RAGAS when ragas package + judge LLM configured
    try:
        from ragas import evaluate  # type: ignore
        from ragas.metrics import faithfulness as ragas_faithfulness  # type: ignore

        print("Native RAGAS available — use scripts/run_native_ragas.py for full dataset runs")
    except ImportError:
        pass

    return 0


if __name__ == "__main__":
    sys.exit(main())

#!/usr/bin/env python3
"""Phase 3 latency benchmarks — lightweight httpx timing (no k6 required)."""
from __future__ import annotations

import argparse
import json
import os
import statistics
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import httpx

from eval_common import (
    API_BASE,
    SKIP_LLM,
    api_reachable,
    chat,
    chat_timeout,
    get_eval_user,
    is_ollama_eval,
    save_report,
)

SLO_DEV = {
    "health_p95_ms": 2000,
    "chat_p95_ms": 90000,
    "corpus_stats_p95_ms": 500,
}

SLO_OLLAMA = {
    "health_p95_ms": 2000,
    "chat_p95_ms": 120000,
    "corpus_stats_p95_ms": 500,
}


def active_slo() -> dict[str, int]:
    return SLO_OLLAMA if is_ollama_eval() else SLO_DEV


def percentile_ms(values: list[float], pct: float) -> float:
    if not values:
        return 0.0
    ordered = sorted(values)
    if len(ordered) == 1:
        return ordered[0] * 1000
    rank = (len(ordered) - 1) * pct
    lo = int(rank)
    hi = min(lo + 1, len(ordered) - 1)
    frac = rank - lo
    return (ordered[lo] * (1 - frac) + ordered[hi] * frac) * 1000


def bench_health(n: int = 20) -> list[float]:
    times: list[float] = []
    with httpx.Client(base_url=API_BASE, timeout=10.0) as client:
        for _ in range(n):
            start = time.perf_counter()
            client.get("/health")
            times.append(time.perf_counter() - start)
    return times


def bench_corpus_stats(token: str, n: int = 10) -> tuple[list[float], int]:
    times: list[float] = []
    failures = 0
    with httpx.Client(base_url=API_BASE, timeout=30.0) as client:
        headers = {"Authorization": f"Bearer {token}"}
        for _ in range(n):
            start = time.perf_counter()
            r = client.get("/api/v1/corpus/stats", headers=headers)
            elapsed = time.perf_counter() - start
            if r.status_code == 200:
                times.append(elapsed)
            else:
                failures += 1
    return times, failures


def bench_chat(
    token: str, n: int = 5, questions: list[str] | None = None
) -> tuple[list[float], int, dict[str, list[float]]]:
    """Time n chats. With ``questions``, ask each one once instead of one GDPR question n times.

    The run number goes into each question so the answer cache never serves it."""
    times: list[float] = []
    stages: dict[str, list[float]] = {}
    failures = 0
    timeout = chat_timeout()
    asked = questions or ["What is GDPR Article 6 lawful processing?"] * n
    for i, question in enumerate(asked):
        start = time.perf_counter()
        r = chat(
            token,
            f"{question} (bench {i})",
            timeout=timeout,
        )
        elapsed = time.perf_counter() - start
        if r.status_code == 200:
            times.append(elapsed)
            for stage, ms in (r.json().get("timings_ms") or {}).items():
                stages.setdefault(stage, []).append(ms / 1000)
        else:
            failures += 1
    return times, failures, stages


def main() -> int:
    parser = argparse.ArgumentParser(description="JurisGuard latency benchmark")
    parser.add_argument("--chat-runs", type=int, default=5)
    parser.add_argument(
        "--questions", type=Path, help="JSONL with a 'question' field: ask each once instead of repeating one question"
    )
    parser.add_argument("--report", type=Path, default=Path("eval/reports/latency_latest.json"))
    parser.add_argument(
        "--warn-only",
        action="store_true",
        help="Record SLO misses but exit 0 (for slow local LLM profiles)",
    )
    args = parser.parse_args()

    if not api_reachable():
        print("API not reachable")
        return 1

    slo = active_slo()
    health_times = bench_health()
    results = {
        "health_ms": {
            "p50": statistics.median(health_times) * 1000 if health_times else 0,
            "p90": percentile_ms(health_times, 0.90),
            "p95": percentile_ms(health_times, 0.95),
        },
    }
    failures: list[str] = []

    if health_times and percentile_ms(health_times, 0.95) > slo["health_p95_ms"]:
        failures.append(f"health p95 {percentile_ms(health_times, 0.95):.0f}ms > {slo['health_p95_ms']}ms")

    if not SKIP_LLM:
        user = get_eval_user()
        token = user["token"]
        corp_times, corp_fail = bench_corpus_stats(token)
        results["corpus_stats_ms"] = {
            "p50": statistics.median(corp_times) * 1000 if corp_times else 0,
            "p90": percentile_ms(corp_times, 0.90),
            "p95": percentile_ms(corp_times, 0.95),
            "http_failures": corp_fail,
        }
        if corp_times and percentile_ms(corp_times, 0.95) > slo["corpus_stats_p95_ms"]:
            failures.append(
                f"corpus p95 {percentile_ms(corp_times, 0.95):.0f}ms > {slo['corpus_stats_p95_ms']}ms"
            )

        questions = (
            [json.loads(line)["question"] for line in args.questions.read_text(encoding="utf-8").splitlines() if line.strip()]
            if args.questions
            else None
        )
        chat_times, chat_fail, stage_times = bench_chat(token, n=args.chat_runs, questions=questions)
        results["stages_ms"] = {
            stage: {"p50": statistics.median(values) * 1000, "p95": percentile_ms(values, 0.95)}
            for stage, values in sorted(stage_times.items())
        }
        results["chat_ms"] = {
            "p50": statistics.median(chat_times) * 1000 if chat_times else 0,
            "p90": percentile_ms(chat_times, 0.90),
            "p95": percentile_ms(chat_times, 0.95),
            "max": max(chat_times) * 1000 if chat_times else 0,
            "runs_requested": len(questions) if questions else args.chat_runs,
            "runs_ok": len(chat_times),
            "http_failures": chat_fail,
            "questions": str(args.questions) if args.questions else "one GDPR question, repeated",
            "samples_s": [round(t, 3) for t in chat_times],
        }
        if chat_times and percentile_ms(chat_times, 0.95) > slo["chat_p95_ms"]:
            failures.append(f"chat p95 {percentile_ms(chat_times, 0.95):.0f}ms > {slo['chat_p95_ms']}ms")
    else:
        results["chat_ms"] = {"skipped": True, "reason": "CI_SKIP_LLM"}

    report = {
        "suite": "latency",
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "results": results,
        "slo": slo,
        "slo_profile": "ollama" if is_ollama_eval() else "dev",
        "llm_provider": os.environ.get("LLM_PROVIDER", "openrouter"),
        "ollama_model": os.environ.get("OLLAMA_MODEL", ""),
        "failures": failures,
    }
    save_report(Path(__file__).resolve().parents[1] / args.report, report)

    print("\n=== Latency Benchmark ===")
    print(json.dumps(results, indent=2))
    if failures:
        for f in failures:
            print(f"  SLO MISS: {f}")
        if args.warn_only or is_ollama_eval():
            print("  (SLO misses recorded; exiting 0 for publishable local LLM profile)")
            return 0
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())

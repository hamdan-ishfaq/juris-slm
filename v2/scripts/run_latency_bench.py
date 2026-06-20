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
    "chat_p95_ms": 900000,
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


def bench_chat(token: str, n: int = 5) -> tuple[list[float], int]:
    times: list[float] = []
    failures = 0
    timeout = chat_timeout()
    for i in range(n):
        start = time.perf_counter()
        r = chat(
            token,
            f"What is GDPR Article 6 lawful processing? (bench {i})",
            timeout=timeout,
            use_hyde=True,
        )
        elapsed = time.perf_counter() - start
        if r.status_code == 200:
            times.append(elapsed)
        else:
            failures += 1
    return times, failures


def main() -> int:
    parser = argparse.ArgumentParser(description="JurisGuard latency benchmark")
    parser.add_argument("--chat-runs", type=int, default=5)
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

        chat_times, chat_fail = bench_chat(token, n=args.chat_runs)
        results["chat_ms"] = {
            "p50": statistics.median(chat_times) * 1000 if chat_times else 0,
            "p90": percentile_ms(chat_times, 0.90),
            "p95": percentile_ms(chat_times, 0.95),
            "runs_requested": args.chat_runs,
            "runs_ok": len(chat_times),
            "http_failures": chat_fail,
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

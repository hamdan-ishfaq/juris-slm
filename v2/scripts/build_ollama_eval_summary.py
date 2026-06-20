#!/usr/bin/env python3
"""Merge latest eval JSON reports into one publishable summary."""
from __future__ import annotations

import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path

V2_ROOT = Path(__file__).resolve().parents[1]
REPORTS = V2_ROOT / "eval" / "reports"


def load_json(name: str) -> dict | None:
    path = REPORTS / name
    if not path.is_file():
        return None
    return json.loads(path.read_text(encoding="utf-8"))


def main() -> int:
    logical = load_json("logical_latest.json")
    ragas = load_json("ragas_latest.json")
    latency = load_json("latency_latest.json")
    offline_only = load_json("offline_latest.json")

    summary = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "llm_provider": os.environ.get("LLM_PROVIDER", "ollama"),
        "ollama_model": os.environ.get("OLLAMA_MODEL", "phi3.5"),
        "embedding_device": os.environ.get("EMBEDDING_DEVICE", "cuda"),
        "reranker_device": os.environ.get("RERANKER_DEVICE", "cuda"),
        "logical": logical,
        "ragas": ragas,
        "latency": latency,
        "offline": offline_only,
    }
    if logical:
        summary["logical_pass_rate"] = logical.get("pass_rate")
        summary["logical_passed"] = logical.get("passed")
        summary["logical_failed"] = logical.get("failed")
    if ragas and ragas.get("metrics"):
        m = ragas["metrics"]
        summary["ragas_metrics"] = m
        summary["ragas_coverage"] = m.get("coverage_rate")
        summary["ragas_complete"] = m.get("complete", False)
    if latency and latency.get("results"):
        summary["latency_chat_p95_ms"] = latency["results"].get("chat_ms", {}).get("p95")

    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    out_latest = REPORTS / "ollama_eval_summary_latest.json"
    out_stamp = REPORTS / f"ollama_eval_summary_{stamp}.json"
    text = json.dumps(summary, indent=2)
    out_latest.write_text(text, encoding="utf-8")
    out_stamp.write_text(text, encoding="utf-8")
    print(text)
    print(f"\nWrote {out_latest} and {out_stamp}")
    return 0


if __name__ == "__main__":
    sys.exit(main())

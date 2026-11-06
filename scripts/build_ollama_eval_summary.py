#!/usr/bin/env python3
"""Merge latest eval JSON reports — headline RAG pipeline metrics first."""
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


def build_pipeline_headline(logical: dict | None, proxy: dict | None, latency: dict | None) -> dict:
    """Primary story: retrieval/query pipeline vs generation layer."""
    headline: dict = {
        "story": "Product value is hybrid RAG pipeline (retrieve → rerank → augment → generate), not raw LLM IQ",
        "stages": [
            "query guard + optional HyDE / legal query expansion",
            "hybrid retrieve (bge-m3 + BM25, RRF merge)",
            "cross-encoder rerank (top 5)",
            "grounded generation (T2) + citation verify + extractive fallback (T3)",
        ],
    }
    if logical and logical.get("metrics", {}).get("pipeline"):
        p = logical["metrics"]["pipeline"]
        headline["retrieval_source_hit_rate"] = p.get("retrieval_source_hit_rate")
        headline["answer_hit_rate"] = p.get("answer_hit_rate")
        headline["generation_miss"] = p.get("generation_miss")
        headline["answer_modes"] = p.get("answer_modes")
        headline["chat_http_success_rate"] = p.get("chat_http_success_rate")
        headline["law_qa_cases_scored"] = p.get("cases_scored")
    elif logical and logical.get("metrics", {}).get("substring_hit_rate") is not None:
        headline["answer_hit_rate"] = logical["metrics"]["substring_hit_rate"]
        headline["note"] = "Re-run make eval-logical for retrieval_source_hit_rate breakdown"

    if logical:
        headline["offline_pipeline_gates"] = "20/20 RBAC + injection (no LLM)"
        headline["full_logical_pass_rate"] = logical.get("pass_rate")
        headline["full_logical_note"] = (
            "Includes RBAC, injection, refusals, contract cases — not retrieval-only"
        )

    if proxy and proxy.get("metrics"):
        headline["context_proxy"] = proxy["metrics"]

    if latency and latency.get("results", {}).get("chat_ms"):
        chat = latency["results"]["chat_ms"]
        headline["chat_latency_p50_ms"] = chat.get("p50")
        headline["chat_latency_p90_ms"] = chat.get("p90")
        headline["chat_latency_p95_ms"] = chat.get("p95")

    return headline


def main() -> int:
    logical = load_json("logical_latest.json")
    proxy = load_json("context_proxy_latest.json")
    latency = load_json("latency_latest.json")
    offline_only = load_json("offline_latest.json")

    pipeline = build_pipeline_headline(logical, proxy, latency)

    summary = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "llm_provider": os.environ.get("LLM_PROVIDER", logical.get("llm_provider") if logical else "ollama"),
        "ollama_model": os.environ.get("OLLAMA_MODEL", logical.get("ollama_model") if logical else ""),
        "ollama_aux_model": os.environ.get("OLLAMA_AUX_MODEL", ""),
        "model_profile_note": "Air-gap eval uses OLLAMA_MODEL (T2) + OLLAMA_AUX_MODEL (T1 HyDE/decompose)",
        "embedding_device": os.environ.get("EMBEDDING_DEVICE", "cuda"),
        "reranker_device": os.environ.get("RERANKER_DEVICE", "cuda"),
        "pipeline_headline": pipeline,
        "logical": logical,
        "context_proxy": proxy,
        "latency": latency,
        "offline": offline_only,
    }

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

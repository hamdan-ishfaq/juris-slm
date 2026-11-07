#!/usr/bin/env python3
"""Judge saved LegalBench dev answers with RAGAS, using a local model other than the generator.

Run `make eval-native`. It first writes the answers with `legalbench.py answers`. This is a secondary
metric: the judge is a small local model, and the retrieval numbers come from the benchmark's own scorer.
"""
from __future__ import annotations

import argparse
import json
import math
import os
import sys
from datetime import datetime, timezone
from pathlib import Path

# RAGAS reports usage over the network unless told not to.
os.environ["RAGAS_DO_NOT_TRACK"] = "true"

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from check_llm_gpu import OLLAMA_URL, env_file_values, gpu_share  # noqa: E402
from eval_common import SKIP_LLM, save_report  # noqa: E402

DEFAULT_ROWS = ROOT / "data" / "benchmarks" / "legalbench" / "ragas_rows.jsonl"
DEFAULT_JUDGE = "llama3.1:8b"
JUDGE_CTX = 8192
EMBEDDER = "BAAI/bge-small-en-v1.5"
METRIC_NAMES = ("faithfulness", "answer_relevancy")


def make_embeddings():
    from fastembed import TextEmbedding
    from langchain_core.embeddings import Embeddings

    class LocalEmbeddings(Embeddings):
        """Runs on the CPU, so it can't push the judge off the GPU."""

        def __init__(self) -> None:
            self.encoder = TextEmbedding(EMBEDDER)

        def embed_documents(self, texts: list[str]) -> list[list[float]]:
            return [vector.tolist() for vector in self.encoder.embed(texts)]

        def embed_query(self, text: str) -> list[float]:
            return self.embed_documents([text])[0]

    return LocalEmbeddings()


def judge_rows(rows: list[dict], judge: str, num_gpu: int) -> list[dict]:
    from langchain_ollama import ChatOllama
    from ragas import EvaluationDataset, RunConfig, evaluate
    from ragas.embeddings import LangchainEmbeddingsWrapper
    from ragas.llms import LangchainLLMWrapper
    from ragas.metrics import answer_relevancy, faithfulness

    dataset = EvaluationDataset.from_list(
        [
            {"user_input": row["query"], "response": row["answer"], "retrieved_contexts": row["contexts"]}
            for row in rows
        ]
    )
    llm = ChatOllama(
        model=judge, base_url=OLLAMA_URL, temperature=0, num_ctx=JUDGE_CTX, num_gpu=num_gpu, num_predict=1024
    )
    result = evaluate(
        dataset,
        metrics=[faithfulness, answer_relevancy],
        llm=LangchainLLMWrapper(llm),
        embeddings=LangchainEmbeddingsWrapper(make_embeddings()),
        run_config=RunConfig(max_workers=1, timeout=600, max_retries=2),
        raise_exceptions=False,
    )
    scored = result.to_pandas().to_dict("records")
    return [
        {"qid": row["qid"], "subset": row["subset"], **{name: score[name] for name in METRIC_NAMES}}
        for row, score in zip(rows, scored)
    ]


def summarise(per_row: list[dict]) -> dict:
    """A row the judge could not score counts as unscored, never as 0 or as a pass."""
    metrics = {}
    for name in METRIC_NAMES:
        values = [row[name] for row in per_row if not math.isnan(row[name])]
        metrics[name] = sum(values) / len(values) if values else None
        metrics[f"{name}_scored"] = len(values)
    return metrics


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--rows", type=Path, default=DEFAULT_ROWS)
    parser.add_argument("--judge", default=DEFAULT_JUDGE)
    parser.add_argument("--report", type=Path, default=ROOT / "eval/reports/ragas_native_latest.json")
    args = parser.parse_args()

    if SKIP_LLM:
        print("CI_SKIP_LLM set, skipping native RAGAS")
        return 0
    if not args.rows.exists():
        print(f"{args.rows} is missing. Run: make eval-native")
        return 1

    config = {**env_file_values(), **os.environ}
    rows = [json.loads(line) for line in args.rows.read_text().splitlines()]
    generators = {row["model"] for row in rows}
    if args.judge in generators:
        print(f"Judge {args.judge} also generated the answers. Choose another with --judge.")
        return 1
    judged = [row for row in rows if row["answer_mode"] == "llm"]
    if not judged:
        print("No LLM answers to judge")
        return 1

    num_gpu = int(config.get("OLLAMA_NUM_GPU") or 99)
    share = gpu_share(args.judge, {"num_predict": 1, "num_ctx": JUDGE_CTX, "num_gpu": num_gpu})
    if share < 1.0:
        print(f"Judge {args.judge} is only {share:.0%} on the GPU")
        return 1

    per_row = judge_rows(judged, args.judge, num_gpu)
    modes: dict[str, int] = {}
    for row in rows:
        modes[row["answer_mode"]] = modes.get(row["answer_mode"], 0) + 1
    metrics = summarise(per_row)
    save_report(
        args.report,
        {
            "suite": "ragas_native",
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "sample": "seeded LegalBench-RAG dev queries; only answers from the LLM are judged",
            "sample_size": len(rows),
            "answer_modes": modes,
            "generator": sorted(generators),
            "judge": args.judge,
            "embedder": EMBEDDER,
            "metrics": metrics,
            "per_query": per_row,
        },
    )
    print(json.dumps({"answer_modes": modes, "metrics": metrics}, indent=1))
    return 0


if __name__ == "__main__":
    sys.exit(main())

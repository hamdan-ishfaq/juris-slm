#!/usr/bin/env python3
"""Reorder GerDaLIR's official BM25 candidates on a seeded sample of queries, and score by its official measures.

The collection has 3.1 million passages, too many to embed on the target machine, so this compares orderings of the
published top-100 candidates per query. It measures German reranking. It does not measure the product's search.

  gerdalir.py sample --split dev     (host: streams the candidates once and keeps the sampled queries)
  gerdalir.py run --split dev        (ML image: writes one ranking per method)
  gerdalir.py score --split dev --output report.json
"""
from __future__ import annotations

import argparse
import gzip
import io
import json
import math
import random
import sys
import tarfile
import time
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
DATA = ROOT / "data" / "benchmarks" / "gerdalir"
MODELS = ROOT / "data" / "models"
BASE_URL = "https://lavis.cs.hs-rm.de/storage/gerdalir/data"
SEED = 20261107
SAMPLE_SIZE = 300
CANDIDATES = 100
MODES = ("bm25", "bge_m3_similarity", "ms_marco", "bge_reranker_v2_m3")


def _tar_member(name: str, member: str) -> str:
    with urllib.request.urlopen(f"{BASE_URL}/{name}", timeout=300) as response:
        with tarfile.open(fileobj=io.BytesIO(response.read()), mode="r:gz") as archive:
            return archive.extractfile(member).read().decode("utf-8")


def _rows(text: str) -> list[list[str]]:
    return [line.split("\t") for line in text.splitlines() if line]


def cmd_sample(args: argparse.Namespace) -> int:
    qrels: dict[str, list[str]] = {}
    for qid, doc in _rows(_tar_member("qrels.tar.gz", f"qrels.{args.split}.tsv")):
        qrels.setdefault(qid, []).append(doc)
    queries = {row[0]: row[1] for row in _rows(_tar_member("queries.tar.gz", f"queries.{args.split}.tsv"))}
    chosen = set(random.Random(SEED).sample(sorted(qrels), SAMPLE_SIZE))
    candidates: dict[str, list[dict]] = {qid: [] for qid in chosen}
    url = f"{BASE_URL}/pass-candidates.{args.split}.tsv.gz"
    with urllib.request.urlopen(url, timeout=600) as response:
        with gzip.open(response, "rt", encoding="utf-8") as stream:
            for count, line in enumerate(stream, 1):
                qid, doc, rank, passage = line.rstrip("\n").split("\t", 3)
                if qid in chosen and int(rank) <= CANDIDATES:
                    candidates[qid].append({"doc": doc, "rank": int(rank), "text": passage})
                if count % 2_000_000 == 0:
                    print(f"  {count:,} rows read", flush=True)
    DATA.mkdir(parents=True, exist_ok=True)
    with (DATA / f"sample_{args.split}.jsonl").open("w", encoding="utf-8") as out:
        for qid in sorted(chosen):
            out.write(json.dumps({"qid": qid, "query": queries[qid], "relevant": qrels[qid], "candidates": candidates[qid]}) + "\n")
    print(f"{len(chosen)} queries saved, {sum(map(len, candidates.values()))} candidates")
    return 0


def _load(split: str) -> list[dict]:
    return [json.loads(line) for line in (DATA / f"sample_{split}.jsonl").read_text(encoding="utf-8").splitlines()]


def _scorer(mode: str):
    """Return a function giving one score per passage, higher is better."""
    if mode == "bm25":
        return lambda _query, passages: [-i for i in range(len(passages))]
    device = "cuda"
    if mode == "bge_m3_similarity":
        from sentence_transformers import SentenceTransformer

        model = SentenceTransformer(str(MODELS / "bge-m3"), device=device, trust_remote_code=True)
        model.max_seq_length = 512

        def score(query: str, passages: list[str]) -> list[float]:
            vectors = model.encode([query, *passages], batch_size=16, normalize_embeddings=True, show_progress_bar=False)
            return (vectors[1:] @ vectors[0]).tolist()

        return score
    from sentence_transformers import CrossEncoder

    path = MODELS / ("reranker" if mode == "ms_marco" else "bge-reranker-v2-m3")
    model = CrossEncoder(str(path), device=device, max_length=512)
    return lambda query, passages: [
        float(value) for value in model.predict([(query, p) for p in passages], batch_size=16, show_progress_bar=False)
    ]


def cmd_run(args: argparse.Namespace) -> int:
    tests = _load(args.split)
    out_dir = DATA / "runs" / args.split
    out_dir.mkdir(parents=True, exist_ok=True)
    for mode in MODES:
        target = out_dir / f"{mode}.json"
        if target.exists():
            print(f"{mode}: already done")
            continue
        score = _scorer(mode)
        rankings: dict[str, list[str]] = {}
        started = time.perf_counter()
        for n, test in enumerate(tests, 1):
            ordered = sorted(test["candidates"], key=lambda c: c["rank"])
            scores = score(test["query"], [c["text"] for c in ordered])
            ranked = sorted(zip(ordered, scores), key=lambda pair: pair[1], reverse=True)
            rankings[test["qid"]] = [c["doc"] for c, _ in ranked]
            if n % 25 == 0:
                print(f"  {mode}: {n}/{len(tests)} {time.perf_counter() - started:.0f}s", flush=True)
        target.write_text(json.dumps(rankings))
        print(f"{mode}: done in {time.perf_counter() - started:.0f}s", flush=True)
    return 0


def _unique(docs: list[str]) -> list[str]:
    """Passage-wise mode from the paper: each passage counts as its document, at its first position."""
    return list(dict.fromkeys(docs))


def _measures(docs: list[str], relevant: set[str]) -> dict[str, float]:
    ranked = _unique(docs)
    mrr = next((1 / i for i, doc in enumerate(ranked[:10], 1) if doc in relevant), 0.0)
    dcg = sum(1 / math.log2(i + 1) for i, doc in enumerate(ranked[:20], 1) if doc in relevant)
    ideal = sum(1 / math.log2(i + 1) for i in range(1, min(len(relevant), 20) + 1))
    recall = len(relevant & set(ranked[:100])) / len(relevant)
    return {"MRR@10": mrr, "nDCG@20": dcg / ideal, "Recall@100": recall}


def _interval(values: list[float], rounds: int = 1000) -> list[float]:
    rng = random.Random(7)
    means = sorted(sum(rng.choices(values, k=len(values))) / len(values) for _ in range(rounds))
    return [round(means[int(0.025 * rounds)], 3), round(means[int(0.975 * rounds)], 3)]


def cmd_score(args: argparse.Namespace) -> int:
    tests = _load(args.split)
    report: dict = {
        "benchmark": "GerDaLIR, passage-wise, official BM25 candidates",
        "split": args.split,
        "queries": len(tests),
        "seed": SEED,
        "candidates_per_query": CANDIDATES,
        "note": "Recall@100 is fixed by the candidates, so it can't differ between methods.",
        "modes": {},
    }
    print(f"GerDaLIR {args.split}, n={len(tests)}, top {CANDIDATES} BM25 candidates")
    print(f"{'method':22s} {'MRR@10':22s} {'nDCG@20':22s} Recall@100")
    for mode in MODES:
        rankings = json.loads((DATA / "runs" / args.split / f"{mode}.json").read_text())
        rows = [_measures(rankings[t["qid"]], set(t["relevant"])) for t in tests]
        result = {}
        for name in rows[0]:
            values = [row[name] for row in rows]
            result[name] = {"mean": round(sum(values) / len(values), 3), "ci95": _interval(values)}
        report["modes"][mode] = result
        cells = [f"{result[n]['mean']:.3f} {result[n]['ci95']}" for n in rows[0]]
        print(f"{mode:22s} {cells[0]:22s} {cells[1]:22s} {cells[2]}")
    Path(args.output).write_text(json.dumps(report, indent=1) + "\n")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)
    for name, func in (("sample", cmd_sample), ("run", cmd_run), ("score", cmd_score)):
        command = sub.add_parser(name)
        command.add_argument("--split", choices=("dev", "test"), required=True)
        if name == "score":
            command.add_argument("--output", required=True)
        command.set_defaults(func=func)
    args = parser.parse_args()
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())

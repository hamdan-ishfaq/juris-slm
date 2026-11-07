#!/usr/bin/env python3
"""Score the pipeline on LegalBench-RAG queries whose documents played no part in tuning.

All tuning used the mini set's dev split. This takes queries from the full benchmark whose documents are outside the
mini set, and searches across every document. The design was committed before any result: seed 20261107, 500 queries
from each sub-dataset with held-out documents, and frozen pipeline settings. Every privacy_qa document is in the mini
set, so that sub-dataset can't be included.

  heldout.py ingest   (ML image, separate database)
  heldout.py run --part tune     (ML image)
  heldout.py bm25 --part tune    (host)
  heldout.py score --part tune --output report.json   (host)
"""
from __future__ import annotations

import argparse
import asyncio
import json
import random
import sys
import uuid
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
import legalbench as lb  # noqa: E402

SEED = 20261107
PER_SUBSET = 500
SUBSETS = ("contractnli", "maud", "cuad")
OUT = lb.RUNS / "heldout"
lb.CHUNKS = lb.DATA / "chunks_full.jsonl"


def all_tests() -> list[dict]:
    tests = []
    for subset in lb.SUBSETS:
        for test in json.loads((lb.BENCHMARKS / f"{subset}.json").read_text())["tests"]:
            tests.append({**test, "subset": subset, "qid": lb.query_id(subset, test)})
    return tests


MINI_DOCUMENTS = {snippet["file_path"] for test in lb.load_mini() for snippet in test["snippets"]}


def held_out_sample() -> list[dict]:
    tests = [t for t in all_tests() if not {s["file_path"] for s in t["snippets"]} & MINI_DOCUMENTS]
    rng = random.Random(SEED)
    sample = []
    for subset in SUBSETS:
        pool = sorted((t for t in tests if t["subset"] == subset), key=lambda t: (t["qid"], t["query"]))
        sample.extend(rng.sample(pool, PER_SUBSET))
    return sample


def second_round(part: str) -> list[dict]:
    """Half the held-out documents for tuning routing at this scale, and half for one final score.

    The first sample's routing errors were read, so its queries are left out. Split by document, drawing queries only from
    the half asked for. Fixed before any tuning: seed 20261108, 250 queries per sub-dataset for tuning and 500 for the
    final score, or as many as exist.
    """
    seen = {(t["qid"], t["query"]) for t in held_out_sample()}
    tests = [t for t in all_tests() if not {s["file_path"] for s in t["snippets"]} & MINI_DOCUMENTS]
    sample = []
    for subset in SUBSETS:
        in_subset = [t for t in tests if t["subset"] == subset]
        documents = sorted({s["file_path"] for t in in_subset for s in t["snippets"]})
        random.Random(f"20261108-split-{subset}").shuffle(documents)
        half = set(documents[: len(documents) // 2]) if part == "tune" else set(documents[len(documents) // 2 :])
        chosen = sorted(
            (
                t
                for t in in_subset
                if {s["file_path"] for s in t["snippets"]} <= half and (t["qid"], t["query"]) not in seen
            ),
            key=lambda t: (t["qid"], t["query"]),
        )
        size = min(250 if part == "tune" else 500, len(chosen))
        sample.extend(random.Random(f"20261108-sample-{subset}-{part}").sample(chosen, size))
    return sample


def all_documents() -> set[uuid.UUID]:
    return {uuid.uuid5(lb.NAMESPACE, s["file_path"]) for t in all_tests() for s in t["snippets"]}


def cmd_ingest(_args: argparse.Namespace) -> int:
    lb.load_mini = all_tests
    stats = asyncio.run(lb._ingest())
    (lb.DATA / "ingest_stats_full.json").write_text(json.dumps(stats, indent=1))
    print(stats)
    return 1 if stats["unlocated"] else 0


def _sample(part: str) -> list[dict]:
    return held_out_sample() if part == "first" else second_round(part)


def _out(part: str) -> Path:
    return OUT if part == "first" else lb.RUNS / f"heldout_{part}"


def cmd_run(args: argparse.Namespace) -> int:
    _out(args.part).mkdir(parents=True, exist_ok=True)
    asyncio.run(lb._run_product_modes(["dense", "product"], _sample(args.part), _out(args.part), documents=all_documents()))
    return 0


def cmd_bm25(args: argparse.Namespace) -> int:
    _out(args.part).mkdir(parents=True, exist_ok=True)
    (_out(args.part) / "bm25.json").write_text(json.dumps(lb._run_bm25(_sample(args.part))))
    return 0


def cmd_score(args: argparse.Namespace) -> int:
    tests = _sample(args.part)
    report: dict = {
        "benchmark": "LegalBench-RAG full set, queries on documents outside the mini set",
        "scorer_commit": lb.SCORER_COMMIT,
        "dataset_sha256": lb.DATASET_SHA256,
        "code_commit": lb._commit(),
        "part": args.part,
        "queries": len(tests),
        "per_subset": PER_SUBSET,
        "documents_searched": len(all_documents()),
        "hardware": lb._hardware(),
        "modes": {},
    }
    lines = ["| Mode | R@1 | R@4 | R@8 | R@16 | R@64 | P@8 |", "|---|---|---|---|---|---|---|"]
    for mode in ("bm25", "dense", "product"):
        results = json.loads((_out(args.part) / f"{mode}.json").read_text())
        by_k = {}
        for k in lb.KS:
            by_k[str(k)] = {"all": lb._score_group(tests, results, k)}
            for subset in SUBSETS:
                by_k[str(k)][subset] = lb._score_group([t for t in tests if t["subset"] == subset], results, k)
        report["modes"][mode] = {"by_k": by_k}
        recall = [by_k[k]["all"]["recall"] * 100 for k in ("1", "4", "8", "16", "64")]
        lines.append(f"| {mode} | " + " | ".join(f"{v:.1f}" for v in recall) + f" | {by_k['8']['all']['precision'] * 100:.1f} |")
    target = Path(args.output)
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps(report, indent=1) + "\n")
    target.with_suffix(".md").write_text("\n".join(lines) + "\n")
    print("\n".join(lines))
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)
    for name, func in (("ingest", cmd_ingest), ("run", cmd_run), ("bm25", cmd_bm25), ("score", cmd_score)):
        command = sub.add_parser(name)
        if name != "ingest":
            command.add_argument("--part", choices=("first", "tune", "final"), required=True)
        if name == "score":
            command.add_argument("--output", required=True)
        command.set_defaults(func=func)
    args = parser.parse_args()
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())

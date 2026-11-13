#!/usr/bin/env python3
"""Second retrieval round: unused queries, queries with the document's name removed, and paired comparisons.

What earlier rounds already used, so it can't give a clean score again:
  - mini dev split: tuned on; mini test split: scored twice, totals only
  - held-out first sample (1,500 queries): its routing errors were read
  - held-out tuning half (648 queries): tuned on
  - held-out final set (1,135 queries): scored once, routing error totals read

Every ContractNLI query on the final-half documents is in one of those, and 4 MAUD queries are left, so only CUAD has
unused queries: all 1,209 of them form the `fresh` set. The final set is scored a second time for ContractNLI and MAUD,
and labelled as such. Sets are fixed here before any run on them; `sets` writes them to round2_sets.json.

The routing variants tuned in this round (searching the documents whose descriptions are nearest the question) were run
from this file at commit 22160c7, by replacing the pipeline's named-document step. The chosen one is now the product's
own (D-015), so `run` measures it directly.

  round2.py sets                                         (host)
  round2.py ingest-plain                                 (ML image, database juris_bench_full_plain)
  round2.py run --set tune --run NAME [--no-names]       (ML image)
  round2.py bm25 --set tune --run NAME [--no-names]      (host)
  round2.py score --set tune --runs a=round2/NAME/product,b=heldout_tune/dense --output report.json   (host)
"""
from __future__ import annotations

import argparse
import asyncio
import json
import random
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
import heldout as h  # noqa: E402

lb = h.lb
SETS_FILE = Path(__file__).parent / "round2_sets.json"
OUT = lb.RUNS / "round2"
PAIRED_SEED = 20261112


def _final_half(subset: str) -> set[str]:
    """The scoring half of the held-out documents, split exactly as heldout.second_round does."""
    tests = [t for t in h.all_tests() if t["subset"] == subset and not {s["file_path"] for s in t["snippets"]} & h.MINI_DOCUMENTS]
    documents = sorted({s["file_path"] for t in tests for s in t["snippets"]})
    random.Random(f"20261108-split-{subset}").shuffle(documents)
    return set(documents[len(documents) // 2 :])


def build_sets() -> dict[str, list[dict]]:
    used = {(t["qid"], t["query"]) for part in ("first", "tune", "final") for t in h._sample(part)}
    half = _final_half("cuad")
    fresh = sorted(
        (
            t
            for t in h.all_tests()
            if t["subset"] == "cuad"
            and {s["file_path"] for s in t["snippets"]} <= half
            and (t["qid"], t["query"]) not in used
        ),
        key=lambda t: (t["qid"], t["query"]),
    )
    return {
        "tune": h.second_round("tune"),
        "final": [t for t in h.second_round("final") if t["subset"] in ("contractnli", "maud")],
        "fresh": fresh,
    }


def load_set(name: str) -> list[dict]:
    """The set as committed, so a later change to the sampling code can't change what gets scored."""
    keys = {tuple(key) for key in json.loads(SETS_FILE.read_text())["sets"][name]}
    tests = [t for t in h.all_tests() if (t["qid"], t["query"]) in keys]
    if len(tests) != len(keys):
        raise SystemExit(f"set {name}: {len(keys)} committed, {len(tests)} found")
    return tests


def without_names(test: dict) -> dict:
    """The query with the clause naming its document removed, as a user who names no document would ask it.

    Every query follows the benchmark's template "Consider <document>; <question>", so the question is what follows the
    first semicolon. The product's own rule (focus_question) depends on the filename holding the name, and left names
    behind in 14 of 648 tuning queries, so it isn't used to build this variant.
    """
    head, sep, question = test["query"].partition(";")
    if not sep or not head.startswith("Consider "):
        raise ValueError(f"query outside the template: {test['qid']}")
    return {**test, "query": question.strip()}


def _tests(args: argparse.Namespace) -> list[dict]:
    tests = load_set(args.set)
    return [without_names(t) for t in tests] if args.no_names else tests


def cmd_sets(_args: argparse.Namespace) -> int:
    sets = build_sets()
    SETS_FILE.write_text(
        json.dumps(
            {
                "note": "Fixed before any run on them. See round2.py for what each set is.",
                "counts": {name: {s: sum(t["subset"] == s for t in tests) for s in h.SUBSETS} for name, tests in sets.items()},
                "sets": {name: [[t["qid"], t["query"]] for t in tests] for name, tests in sets.items()},
            },
            indent=1,
        )
        + "\n"
    )
    for name, tests in sets.items():
        print(name, len(tests))
    return 0


def cmd_ingest_plain(_args: argparse.Namespace) -> int:
    """Every document again, without its name in the chunk embeddings: the plain vector search baseline."""
    import services.contextual_retrieval as cr

    original = cr.build_embedding_text
    cr.build_embedding_text = lambda content, metadata: original(content, {k: v for k, v in metadata.items() if k != "title"})
    lb.CHUNKS = lb.DATA / "chunks_full_plain.jsonl"
    lb.load_mini = h.all_tests
    stats = asyncio.run(lb._ingest())
    (lb.DATA / "ingest_stats_full_plain.json").write_text(json.dumps(stats, indent=1))
    print(stats)
    return 1 if stats["unlocated"] else 0


async def _run_chosen(tests: list[dict]) -> dict[str, dict]:
    """The pipeline as used when the user picks the document in the interface and asks without naming it."""
    import time

    from db import async_session_factory
    from services.rag import _retrieve_and_rank

    results: dict[str, dict] = {}
    async with async_session_factory() as db:
        for n, test in enumerate(tests):
            started = time.perf_counter()
            hits = await _retrieve_and_rank(
                db,
                test["query"],
                accessible_ids=h.all_documents(),
                include_law=False,
                user_role="owner",
                doc_uuid=lb.uuid.uuid5(lb.NAMESPACE, test["snippets"][0]["file_path"]),
                use_hyde=False,
            )
            results[test["qid"]] = {"spans": lb._spans_from_hits(hits), "seconds": round(time.perf_counter() - started, 4)}
            if (n + 1) % 100 == 0:
                print(f"  chosen: {n + 1}/{len(tests)}", flush=True)
    return results


def cmd_run(args: argparse.Namespace) -> int:
    out = OUT / args.run
    out.mkdir(parents=True, exist_ok=True)
    tests = _tests(args)
    if args.modes == "chosen":
        from config import settings

        settings.rag_rerank_k = settings.rag_top_k
        (out / "chosen.json").write_text(json.dumps(asyncio.run(_run_chosen(tests))))
        return 0
    asyncio.run(lb._run_product_modes(args.modes.split(","), tests, out, documents=h.all_documents()))
    return 0


def cmd_bm25(args: argparse.Namespace) -> int:
    out = OUT / args.run
    out.mkdir(parents=True, exist_ok=True)
    (out / "bm25.json").write_text(json.dumps(lb._run_bm25(_tests(args))))
    return 0


def _paired(tests: list[dict], a: dict, b: dict, k: int) -> dict:
    """Mean per-query recall difference a minus b, with a bootstrap interval over queries."""
    ra, _ = lb._per_query(tests, a, k)
    rb, _ = lb._per_query(tests, b, k)
    diffs = [x - y for x, y in zip(ra, rb)]
    return {"difference": round(sum(diffs) / len(diffs), 4), "ci95": lb._interval(diffs, seed=PAIRED_SEED)}


def cmd_score(args: argparse.Namespace) -> int:
    """Aggregates only, per sub-dataset, so no single query's result is read."""
    tests = load_set(args.set)
    subsets = [s for s in h.SUBSETS if any(t["subset"] == s for t in tests)]
    runs = dict(pair.split("=", 1) for pair in args.runs.split(","))
    results = {name: json.loads((lb.RUNS / f"{path}.json").read_text()) for name, path in runs.items()}
    report: dict = {
        "benchmark": "LegalBench-RAG full set, 714 documents searched",
        "set": args.set,
        "queries": len(tests),
        "scorer_commit": lb.SCORER_COMMIT,
        "code_commit": lb._commit(),
        "hardware": lb._hardware(),
        "runs": runs,
        "modes": {},
        "paired_recall_at_8": {},
    }
    lines = [
        "| Run | R@1 | R@4 | R@8 | R@8 95% | P@8 | " + " | ".join(f"{s} R@8" for s in subsets) + " |",
        "|---|---|---|---|---|---|" + "---|" * len(subsets),
    ]
    for name, result in results.items():
        by_k = {str(k): {"all": lb._score_group(tests, result, k)} for k in lb.KS}
        for s in subsets:
            by_k["8"][s] = lb._score_group([t for t in tests if t["subset"] == s], result, 8)
        report["modes"][name] = {"by_k": by_k}
        r8 = by_k["8"]["all"]
        lines.append(
            f"| {name} | {by_k['1']['all']['recall'] * 100:.1f} | {by_k['4']['all']['recall'] * 100:.1f} | "
            f"{r8['recall'] * 100:.1f} | {r8['recall_ci95'][0] * 100:.1f}-{r8['recall_ci95'][1] * 100:.1f} | "
            f"{r8['precision'] * 100:.1f} | " + " | ".join(f"{by_k['8'][s]['recall'] * 100:.1f}" for s in subsets) + " |"
        )
    names = list(results)
    if len(names) > 1:
        lines += ["", "| Paired R@8 | Difference | 95% |", "|---|---|---|"]
        for other in names[1:]:
            paired = _paired(tests, results[names[0]], results[other], 8)
            report["paired_recall_at_8"][f"{names[0]} - {other}"] = paired
            lines.append(
                f"| {names[0]} - {other} | {paired['difference'] * 100:+.1f} | "
                f"{paired['ci95'][0] * 100:+.1f} to {paired['ci95'][1] * 100:+.1f} |"
            )
    target = Path(args.output)
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps(report, indent=1) + "\n")
    target.with_suffix(".md").write_text("\n".join(lines) + "\n")
    print("\n".join(lines))
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("sets").set_defaults(func=cmd_sets)
    sub.add_parser("ingest-plain").set_defaults(func=cmd_ingest_plain)
    for name, func in (("run", cmd_run), ("bm25", cmd_bm25)):
        command = sub.add_parser(name)
        command.add_argument("--set", choices=("tune", "final", "fresh"), required=True)
        command.add_argument("--run", required=True)
        command.add_argument("--no-names", action="store_true")
        if name == "run":
            command.add_argument("--modes", default="dense,product")
        command.set_defaults(func=func)
    score = sub.add_parser("score")
    score.add_argument("--set", choices=("tune", "final", "fresh"), required=True)
    score.add_argument("--runs", required=True, help="name=path/mode under runs/,... ; the first is compared with each of the others")
    score.add_argument("--output", required=True)
    score.set_defaults(func=cmd_score)
    args = parser.parse_args()
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())

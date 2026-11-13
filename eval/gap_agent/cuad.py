#!/usr/bin/env python3
"""Score gap analysis on CUAD: which of 10 clause types each contract has, as fixed in README.md before any result.

  cuad.py run --method agent|one_call --set dev|test --run NAME   (ML image, juris_bench_full; resumes)

The rule-based tool this replaced was run with this file at commit 856e296, which still had it; its results are kept in
eval/reports/gap_agent_2026-11/.
  cuad.py score --set dev|test --runs NAME/agent,NAME/one_call,NAME/rule --output report.json   (host)
"""
from __future__ import annotations

import argparse
import asyncio
import json
import random
import re
import sys
import time
import uuid
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "backend" / "src"))
sys.path.insert(0, str(ROOT / "eval" / "legalbench"))
CUAD = ROOT / "data" / "benchmarks" / "cuad" / "CUAD_v1" / "CUAD_v1.json"
RUNS = ROOT / "data" / "benchmarks" / "cuad" / "runs"
SETS = Path(__file__).parent / "sets.json"
ONE_CALL_CHARS = 9000


def _contracts(name: str) -> list[tuple[str, str]]:
    return [tuple(pair) for pair in json.loads(SETS.read_text())[name]]


def gold(titles: set[str]) -> dict[str, dict]:
    """For each contract: its text, and for each checked clause type the CUAD answer spans (empty when absent)."""
    from services.agents.contract_review import COMMERCIAL_CHECKLIST

    by_label = {item.label: item.key for item in COMMERCIAL_CHECKLIST}
    out: dict[str, dict] = {}
    for doc in json.loads(CUAD.read_text())["data"]:
        if doc["title"] not in titles:
            continue
        paragraph = doc["paragraphs"][0]
        spans = {}
        for qa in paragraph["qas"]:
            key = by_label.get(qa["id"].split("__")[-1])
            if key:
                spans[key] = [(a["answer_start"], a["answer_start"] + len(a["text"])) for a in qa["answers"]]
        out[doc["title"]] = {"text": paragraph["context"], "spans": spans}
    return out


def _document_id(legalbench_file: str) -> uuid.UUID:
    import legalbench as lb

    return uuid.uuid5(lb.NAMESPACE, f"cuad/{legalbench_file}")


async def _run_contract(method: str, title: str, file: str, text: str) -> dict:
    from db import async_session_factory
    from services.agents.contract_review import COMMERCIAL_CHECKLIST, check_item, review_contract

    started = time.perf_counter()
    if method == "agent":
        async with async_session_factory() as db:
            review = await review_contract(db, _document_id(file), checklist=COMMERCIAL_CHECKLIST)
        items = {r.key: {"status": r.status, "quote": r.quote, "calls": r.calls, "error": r.error} for r in review.items}
    elif method == "one_call":
        opening = [{"id": "opening", "content": text[:ONE_CALL_CHARS], "metadata": {"title": title}}]
        items = {}
        for item in COMMERCIAL_CHECKLIST:
            from services.agents.contract_review import _ollama_ask

            r = await check_item(item, opening, ask=_ollama_ask, calls_left=2)
            items[item.key] = {"status": r.status, "quote": r.quote, "calls": r.calls, "error": r.error}
    else:
        raise ValueError(method)
    return {"title": title, "items": items, "seconds": round(time.perf_counter() - started, 2)}


async def cmd_run(args: argparse.Namespace) -> int:
    contracts = _contracts(args.set)
    texts = gold({title for title, _ in contracts})
    out = RUNS / args.run / args.method
    out.mkdir(parents=True, exist_ok=True)
    for n, (title, file) in enumerate(contracts, 1):
        target = out / f"{re.sub(r'[^A-Za-z0-9]+', '_', title)[:120]}.json"
        if target.exists():
            continue  # resume
        result = await _run_contract(args.method, title, file, texts[title]["text"])
        target.write_text(json.dumps(result))
        print(f"  {args.method} {n}/{len(contracts)} {result['seconds']}s", flush=True)
    return 0


def _quote_span(quote: str, text: str) -> tuple[int, int] | None:
    """Where a quote sits in the contract, matching its words across any spacing or punctuation."""
    words = re.findall(r"[A-Za-z0-9]+", quote)
    if len(words) < 3:
        return None
    match = re.search(r"\W+".join(map(re.escape, words)), text, re.IGNORECASE)
    return (match.start(), match.end()) if match else None


def _score(contracts: list[tuple[str, str]], truth: dict, results: dict) -> dict:
    """Missing-clause precision and recall, accuracy and quote overlap, with intervals over contracts."""
    rows = []  # per contract: counts
    for title, _ in contracts:
        r = results.get(title)
        if r is None:
            continue
        counts = dict(tp_missing=0, fp_missing=0, fn_missing=0, correct=0, decided=0, not_checked=0,
                      present_both=0, quote_hit=0, calls=0)
        for key, spans in truth[title]["spans"].items():
            item = r["items"][key]
            counts["calls"] += item["calls"]
            if item["status"] == "not_checked":
                counts["not_checked"] += 1
            said_missing = item["status"] in ("missing", "not_checked")
            absent = not spans
            counts["decided"] += 1
            counts["correct"] += said_missing == absent
            counts["tp_missing"] += said_missing and absent
            counts["fp_missing"] += said_missing and not absent
            counts["fn_missing"] += (not said_missing) and absent
            if not said_missing and not absent:
                counts["present_both"] += 1
                where = _quote_span(item["quote"], truth[title]["text"])
                counts["quote_hit"] += bool(where and any(where[0] < e and s < where[1] for s, e in spans))
        rows.append(counts)

    def ratio(num, den, sample):
        n, d = sum(x[num] for x in sample), sum(x[den] if isinstance(den, str) else den(x) for x in sample)
        return n / d if d else 0.0

    def boot(fn):
        rng = random.Random(7)
        vals = sorted(fn([rows[rng.randrange(len(rows))] for _ in rows]) for _ in range(1000))
        return [round(vals[25], 4), round(vals[975], 4)]

    precision = lambda s: ratio("tp_missing", lambda x: x["tp_missing"] + x["fp_missing"], s)
    recall = lambda s: ratio("tp_missing", lambda x: x["tp_missing"] + x["fn_missing"], s)
    accuracy = lambda s: ratio("correct", "decided", s)
    quote = lambda s: ratio("quote_hit", "present_both", s)
    return {
        "contracts": len(rows),
        "decisions": sum(x["decided"] for x in rows),
        "missing_precision": round(precision(rows), 4), "missing_precision_ci95": boot(precision),
        "missing_recall": round(recall(rows), 4), "missing_recall_ci95": boot(recall),
        "accuracy": round(accuracy(rows), 4), "accuracy_ci95": boot(accuracy),
        "quote_found": round(quote(rows), 4),
        "false_alarms": sum(x["fp_missing"] for x in rows),
        "not_checked": sum(x["not_checked"] for x in rows),
        "calls_per_contract": round(sum(x["calls"] for x in rows) / max(len(rows), 1), 2),
    }


def cmd_score(args: argparse.Namespace) -> int:
    contracts = _contracts(args.set)
    truth = gold({title for title, _ in contracts})
    report: dict = {"set": args.set, "contracts": len(contracts), "methods": {}, "per_clause": {}}
    lines = ["| Method | Accuracy | Missing: precision | Missing: recall | False alarms | Quote found | Calls / contract | s / contract |",
             "|---|---|---|---|---|---|---|---|"]
    from services.agents.contract_review import COMMERCIAL_CHECKLIST

    paths = args.runs.split(",") + ["always_missing"]
    for path in paths:
        results = {}
        if path == "always_missing":
            # The trivial reference: report every clause missing.
            results = {
                title: {"title": title, "seconds": 0.0, "items": {
                    item.key: {"status": "missing", "quote": "", "calls": 0, "error": None} for item in COMMERCIAL_CHECKLIST
                }}
                for title, _ in contracts
            }
        for f in (RUNS / path).glob("*.json") if path != "always_missing" else []:
            r = json.loads(f.read_text())
            results[r["title"]] = r
        s = _score(contracts, truth, results)
        seconds = [r["seconds"] for r in results.values()]
        s["seconds_per_contract"] = round(sum(seconds) / max(len(seconds), 1), 1)
        report["methods"][path] = s
        report["per_clause"][path] = {
            item.key: _score(contracts, {t: {**v, "spans": {item.key: v["spans"][item.key]}} for t, v in truth.items()}, results)["accuracy"]
            for item in COMMERCIAL_CHECKLIST
        }
        lines.append(
            f"| {path} | {s['accuracy'] * 100:.1f}% [{s['accuracy_ci95'][0] * 100:.1f}, {s['accuracy_ci95'][1] * 100:.1f}] | "
            f"{s['missing_precision'] * 100:.1f}% | {s['missing_recall'] * 100:.1f}% | {s['false_alarms']} | "
            f"{s['quote_found'] * 100:.1f}% | {s['calls_per_contract']} | {s['seconds_per_contract']} |"
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
    run = sub.add_parser("run")
    run.add_argument("--method", choices=("agent", "one_call"), required=True)
    run.add_argument("--set", choices=("dev", "test"), required=True)
    run.add_argument("--run", required=True)
    run.set_defaults(func=lambda a: asyncio.run(cmd_run(a)))
    score = sub.add_parser("score")
    score.add_argument("--set", choices=("dev", "test"), required=True)
    score.add_argument("--runs", required=True)
    score.add_argument("--output", required=True)
    score.set_defaults(func=cmd_score)
    args = parser.parse_args()
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())

"""Check the harness against the benchmark scorer on dev queries that have real overlap.

Run on the host from the repo folder: .venv/bin/python <this file>

The scorer sums per-snippet overlap and doesn't merge retrieved spans, so overlapping chunks would
be counted twice. Hand values are computed both ways: plain character sets, and per-snippet sums.
"""
import json
import random
import sys
from pathlib import Path

sys.path.insert(0, "eval/legalbench")
import legalbench as lb

sys.path.insert(0, str(lb.VENDOR / f"legalbenchrag-{lb.SCORER_COMMIT}"))
from legalbenchrag.benchmark_types import QAGroundTruth, RetrievedSnippet
from legalbenchrag.run_benchmark import QAResult

assignment = json.loads(lb.SPLIT.read_text())["assignment"]
dev = [t for t in lb.load_mini() if assignment[t["qid"]] == "dev"]
results = json.loads((lb.RUNS / "baseline" / "bm25.json").read_text())
chunks = [json.loads(line) for line in lb.CHUNKS.read_text(encoding="utf-8").splitlines()]


def chars(snippets) -> set:
    return {(s["file_path"], i) for s in snippets for i in range(s["span"][0], s["span"][1])}


def scored(test, spans) -> QAResult:
    return QAResult(
        qa_gt=QAGroundTruth(query=test["query"], snippets=test["snippets"], tags=[test["subset"]]),
        retrieved_snippets=[
            RetrievedSnippet(file_path=s["file_path"], span=tuple(s["span"]), score=0.0) for s in spans
        ],
    )


# Every stored span must be exactly its chunk's text.
span_mismatch = 0
texts: dict[str, str] = {}
for chunk in chunks:
    if chunk["span"]:
        body = texts.setdefault(chunk["file_path"], (lb.CORPUS / chunk["file_path"]).read_text())
        span_mismatch += body[chunk["span"][0] : chunk["span"][1]] != chunk["content"]

# How often do chunks overlap, and can double counting push recall above 1?
by_doc: dict[str, list] = {}
for chunk in chunks:
    if chunk["span"]:
        by_doc.setdefault(chunk["file_path"], []).append(chunk["span"])
overlapping = 0
overlap_chars = 0
for spans in by_doc.values():
    spans.sort()
    for a, b in zip(spans, spans[1:]):
        if b[0] < a[1]:
            overlapping += 1
            overlap_chars += a[1] - b[0]
max_recall = max(scored(t, results[t["qid"]]["spans"][:64]).recall for t in dev)

with_overlap = [t for t in dev if scored(t, results[t["qid"]]["spans"][:16]).recall > 0]
picks = random.Random(5).sample(with_overlap, 5)
rows = []
for test in picks:
    for k in (4, 16, 64):
        spans = results[test["qid"]]["spans"][:k]
        gold, got = chars(test["snippets"]), chars(spans)
        total_len = sum(s["span"][1] - s["span"][0] for s in spans)
        common = sum(
            max(0, min(s["span"][1], g["span"][1]) - max(s["span"][0], g["span"][0]))
            for s in spans
            for g in test["snippets"]
            if s["file_path"] == g["file_path"]
        )
        gold_len = sum(g["span"][1] - g["span"][0] for g in test["snippets"])
        result = scored(test, spans)
        rows.append(
            {
                "qid": test["qid"],
                "subset": test["subset"],
                "k": k,
                "gold_chars": gold_len,
                "retrieved_chars": total_len,
                "overlap_chars": common,
                "hand_recall": round(common / gold_len, 6),
                "scorer_recall": round(result.recall, 6),
                "hand_precision": round(common / total_len, 6) if total_len else 0.0,
                "scorer_precision": round(result.precision, 6),
                "set_recall": round(len(gold & got) / len(gold), 6),
                "set_precision": round(len(gold & got) / len(got), 6) if got else 0.0,
            }
        )
summary = {
    "dev_queries": len(dev),
    "dev_queries_with_recall_at_16_above_zero": len(with_overlap),
    "chunks": len(chunks),
    "span_text_mismatches": span_mismatch,
    "adjacent_chunk_pairs_overlapping": overlapping,
    "chars_in_overlaps": overlap_chars,
    "max_recall_at_64_on_dev": round(max_recall, 6),
    "scorer_matches_hand": all(
        abs(r["hand_recall"] - r["scorer_recall"]) < 1e-6
        and abs(r["hand_precision"] - r["scorer_precision"]) < 1e-6
        for r in rows
    ),
    "scorer_matches_character_sets": all(
        abs(r["set_recall"] - r["scorer_recall"]) < 1e-6
        and abs(r["set_precision"] - r["scorer_precision"]) < 1e-6
        for r in rows
    ),
}
Path(__file__).with_suffix(".json").write_text(json.dumps({"summary": summary, "rows": rows}, indent=1) + "\n")
print(json.dumps(summary, indent=1))
for row in rows:
    print({k: row[k] for k in ("subset", "k", "gold_chars", "overlap_chars", "scorer_recall", "set_recall", "scorer_precision", "set_precision")})

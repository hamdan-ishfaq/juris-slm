#!/usr/bin/env python3
"""Contract chunk size and overlap, compared on the LegalBench-RAG mini dev split (189 queries, 72 documents).

The product chunker (services/advanced_chunking.py) splits sections into paragraphs and cuts any paragraph longer than
600 characters every 600 characters, mid-word, with no overlap. Each variant here keeps its section and paragraph rules
and changes only how long paragraphs are cut: at a space, to at most `child_max` characters, repeating the last
`overlap` characters. Each variant is ingested into its own database.

Recall@k counts chunks, so larger chunks see more text at the same k. Scores are also given at a fixed budget of
characters, about what eight current chunks hold, so sizes are compared on the text the model would read.

  chunking.py ingest --child-max 400 --overlap 0     (ML image, DATABASE_URL of that variant's database)
  chunking.py run --child-max 400 --overlap 0        (ML image, same database)
  chunking.py bm25 --child-max 400 --overlap 0       (host)
  chunking.py score --variants current,c400_o0 --output report.json   (host)
"""
from __future__ import annotations

import argparse
import asyncio
import json
import re
import sys
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).parent))
import legalbench as lb  # noqa: E402

OUT = lb.RUNS / "chunking"
CHAR_BUDGET = 4800
MIN_CHUNK = 50


def _name(child_max: int, overlap: int) -> str:
    return f"c{child_max}_o{overlap}"


def _windows(para: str, size: int, overlap: int) -> list[str]:
    """Pieces of at most `size` characters, cut at a space, each repeating the last `overlap` characters of the one before."""
    pieces = []
    start = 0
    while start < len(para):
        end = min(len(para), start + size)
        if end < len(para):
            cut = para.rfind(" ", start + size // 2, end)
            end = cut if cut > start else end
        pieces.append(para[start:end].strip())
        if end >= len(para):
            break
        if overlap:
            space = para.find(" ", max(end - overlap, start + 1), end)
            start = space + 1 if space != -1 else end
        else:
            start = end
    return pieces


def variant_chunker(child_max: int, overlap: int):
    """The product chunker with only its long-paragraph cut changed."""
    section_pattern = re.compile(
        r"\n(?=(?:Article|Section|ARTICLE|SECTION)\s+\d+|(?:\d+\.\s+[A-Z][A-Za-z\s]{2,40})\n)", re.IGNORECASE
    )

    def chunk(text: str, **_kwargs: Any) -> list[dict[str, Any]]:
        text = re.sub(r"\n{3,}", "\n\n", text.strip())
        if not text:
            return []
        sections = section_pattern.split(text)
        chunks = []
        for parent_idx, section in enumerate(s.strip() for s in sections):
            if not section:
                continue
            parent_title = section.split("\n", 1)[0].strip()[:120]
            child_idx = 0
            for para in re.split(r"\n\n+", section):
                para = para.strip()
                if len(para) < MIN_CHUNK:
                    continue
                for piece in _windows(para, child_max, overlap) if len(para) > child_max else [para]:
                    if len(piece) >= MIN_CHUNK:
                        chunks.append(
                            {
                                "content": piece,
                                "parent_content": section,
                                "parent_id": f"parent-{parent_idx}",
                                "parent_title": parent_title,
                                "child_index": child_idx,
                            }
                        )
                        child_idx += 1
        return chunks

    return chunk


def _dev_tests() -> list[dict]:
    assignment = json.loads(lb.SPLIT.read_text())["assignment"]
    return [t for t in lb.load_mini() if assignment[t["qid"]] == "dev"]


def _use_variant(args: argparse.Namespace) -> str:
    if getattr(args, "product", False):
        lb.CHUNKS = lb.DATA / "chunks_product.jsonl"
        return "product"
    name = _name(args.child_max, args.overlap)
    lb.CHUNKS = lb.DATA / f"chunks_{name}.jsonl"
    return name


def cmd_ingest(args: argparse.Namespace) -> int:
    import services.advanced_chunking as chunking

    if args.product:
        # The unmodified product chunker, ingested the same way as the variants, so device and order can't differ.
        name = "product"
        lb.CHUNKS = lb.DATA / "chunks_product.jsonl"
    else:
        name = _use_variant(args)
        chunking.hierarchical_chunk = variant_chunker(args.child_max, args.overlap)
    stats = asyncio.run(lb._ingest())
    (lb.DATA / f"ingest_stats_{name}.json").write_text(json.dumps(stats, indent=1))
    print(stats)
    return 1 if stats["unlocated"] else 0


def cmd_run(args: argparse.Namespace) -> int:
    name = "current" if args.current else _use_variant(args)
    out = OUT / (args.output_name or name)
    out.mkdir(parents=True, exist_ok=True)
    asyncio.run(lb._run_product_modes(args.modes.split(","), _dev_tests(), out))
    return 0


def cmd_bm25(args: argparse.Namespace) -> int:
    name = "current" if args.current else _use_variant(args)
    out = OUT / name
    out.mkdir(parents=True, exist_ok=True)
    (out / "bm25.json").write_text(json.dumps(lb._run_bm25(_dev_tests())))
    return 0


def _within_budget(results: dict, budget: int) -> dict:
    """The retrieved spans in order, up to `budget` characters, the last one cut to fit."""
    cut = {}
    for qid, result in results.items():
        spans, used = [], 0
        for span in result.get("spans", []):
            start, end = span["span"]
            if used >= budget:
                break
            take = min(end - start, budget - used)
            spans.append({"file_path": span["file_path"], "span": [start, start + take]})
            used += take
        cut[qid] = {"spans": spans}
    return cut


def cmd_score(args: argparse.Namespace) -> int:
    tests = _dev_tests()
    report: dict = {
        "benchmark": "LegalBench-RAG mini, dev split",
        "queries": len(tests),
        "char_budget": CHAR_BUDGET,
        "scorer_commit": lb.SCORER_COMMIT,
        "code_commit": lb._commit(),
        "variants": {},
    }
    lines = [
        f"| Variant | Mode | Chunks | R@8 | P@8 | R at {CHAR_BUDGET} chars | 95% | P at {CHAR_BUDGET} chars |",
        "|---|---|---|---|---|---|---|---|",
    ]
    for variant in args.variants.split(","):
        stats_file = lb.DATA / ("ingest_stats.json" if variant == "current" else f"ingest_stats_{variant}.json")
        chunks = json.loads(stats_file.read_text())["chunks"]
        report["variants"][variant] = {"chunks": chunks, "modes": {}}
        for mode in args.modes.split(","):
            results = json.loads((OUT / variant / f"{mode}.json").read_text())
            at8 = lb._score_group(tests, results, 8)
            budget = lb._score_group(tests, _within_budget(results, CHAR_BUDGET), max(lb.KS))
            report["variants"][variant]["modes"][mode] = {"at_8": at8, "at_budget": budget}
            lines.append(
                f"| {variant} | {mode} | {chunks} | {at8['recall'] * 100:.1f} | {at8['precision'] * 100:.1f} | "
                f"{budget['recall'] * 100:.1f} | {budget['recall_ci95'][0] * 100:.1f}-{budget['recall_ci95'][1] * 100:.1f} | "
                f"{budget['precision'] * 100:.1f} |"
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
    for name, func in (("ingest", cmd_ingest), ("run", cmd_run), ("bm25", cmd_bm25)):
        command = sub.add_parser(name)
        command.add_argument("--child-max", type=int, default=600)
        command.add_argument("--overlap", type=int, default=0)
        command.add_argument("--product", action="store_true", help="the unmodified product chunker, ingested afresh")
        if name != "ingest":
            command.add_argument("--current", action="store_true", help="the product chunker, in the juris_bench database")
        if name == "run":
            command.add_argument("--modes", default="dense,product")
            command.add_argument("--output-name", help="run folder, if not the variant's own")
        command.set_defaults(func=func)
    score = sub.add_parser("score")
    score.add_argument("--variants", required=True)
    score.add_argument("--modes", default="dense,product")
    score.add_argument("--output", required=True)
    score.set_defaults(func=cmd_score)
    args = parser.parse_args()
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())

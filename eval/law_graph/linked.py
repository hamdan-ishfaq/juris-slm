#!/usr/bin/env python3
"""Does the provision a question depends on reach the model? On the project's 20 linked-provision questions (D-016).

Each question cites one provision, and its answer is in another that the cited one links to in the law text
(eval/golden/linked_provisions.jsonl, written before the graph was used). This runs the pipeline's own retrieval step,
`rag._prepare`, and records which provisions reach the model: the ranked chunks that fit the context cap, plus, on code
from before the graph, the text the old `dlg.py` appended. The project's own questions, not a benchmark. The "before" run
uses the code at commit cbee59a with this file mounted over it.

  linked.py --set dev|heldout --output report.json     (ML image, law corpus database)

The first 20 questions were read while the graph step was being designed, so they are development data. The 15 in
linked_provisions_heldout.jsonl were written and committed before the changes that followed, and are scored once.
"""
from __future__ import annotations

import argparse
import asyncio
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "backend" / "src"))
SETS = {"dev": "linked_provisions.jsonl", "heldout": "linked_provisions_heldout.jsonl"}


def _provision(hit: dict) -> str:
    meta = hit.get("metadata") or {}
    return f"{meta.get('source')}:{meta.get('article')}"


async def _dlg_provisions(db, question: str) -> list[str]:
    """What the old dlg.py appended, by provision, on code that still has it."""
    try:
        from services import dlg
    except ImportError:
        return []
    import re

    found = []
    for number in re.findall(r"(?:article|art\.?)\s*(\d+)", question, re.IGNORECASE)[:3]:
        for chunk in (await dlg._find_law_chunks(db, f"Art. {number}"))[:1]:
            found.append(_provision(chunk))
    return found


async def main(output: Path, questions: str) -> int:
    from db import async_session_factory
    from services import rag

    items = [json.loads(line) for line in (ROOT / "eval" / "golden" / SETS[questions]).read_text().splitlines()]
    rows = []
    async with async_session_factory() as db:
        for item in items:
            prepared = await rag._prepare(
                db, item["question"], use_law_corpus=True, document_id=None, user=None,
                use_hyde=False, multi_query=False, skip_cache=True,
            )
            # Only the chunks _format_context fitted reach the model; its sources name them.
            sent = {source["chunk_id"] for source in prepared.get("sources", [])}
            ranked = [hit for hit in prepared.get("ranked", []) if str(hit.get("id")) in sent]
            provisions = [_provision(hit) for hit in ranked]
            graph = [hit["metadata"].get("graph_path") for hit in ranked if (hit.get("metadata") or {}).get("graph_path")]
            dlg = await _dlg_provisions(db, item["question"])
            in_context = set(provisions) | set(dlg)
            rows.append(
                {
                    "id": item["id"],
                    "refused": "result" in prepared,
                    "cited_in_context": item["cites"] in in_context,
                    "gold_in_context": item["gold"] in in_context,
                    "provisions": provisions,
                    "dlg": dlg,
                    "graph_paths": graph,
                }
            )
            print(item["id"], "gold" if rows[-1]["gold_in_context"] else "----", provisions, graph, flush=True)
    summary = {
        "questions": len(rows),
        "gold_in_context": sum(r["gold_in_context"] for r in rows),
        "cited_in_context": sum(r["cited_in_context"] for r in rows),
        "refused": sum(r["refused"] for r in rows),
    }
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps({"summary": summary, "rows": rows}, indent=1) + "\n")
    print(summary)
    return 0


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--set", default="dev", choices=tuple(SETS))
    args = parser.parse_args()
    sys.exit(asyncio.run(main(args.output, args.set)))

"""H4 and H6 on contracts: what would _format_context build for the chunks the product retrieved?

Applies the product's parent_content and cap logic to the top rag_rerank_k hits of the baseline
product run, using the real parent text from the product chunker. The benchmark database leaves
parent_content out, so this replays assembly rather than querying it. Reports aggregates only.

Run on the host from the repo folder: .venv/bin/python <this file>
"""
import json
import sys
from pathlib import Path
from statistics import median

sys.path.insert(0, "backend/src")
sys.path.insert(0, "eval/legalbench")
import legalbench as lb
from services.advanced_chunking import hierarchical_chunk

CAP = 6000  # rag_max_context_chars
TOP = 5  # rag_rerank_k
NUM_CTX = 4096  # Ollama default seen in its log
# Measured on the law replay: prompt_eval_count / prompt_chars.
results = json.loads((lb.RUNS / "baseline" / "product.json").read_text())
mini = lb.load_mini()
law = json.loads(Path(__file__).with_name("h2_h4_replay.json").read_text())
chars_per_token = sum(r["prompt_chars"] for r in law) / sum(r["prompt_eval_count"] for r in law)

parents: dict[tuple, int] = {}
parent_lengths: list[int] = []
for path in sorted({s["file_path"] for t in mini for s in t["snippets"]}):
    body = (lb.CORPUS / path).read_text()
    items = hierarchical_chunk(body)
    for item, span in zip(items, lb.locate_chunks(body, items)):
        length = len(item.get("parent_content") or item["content"])
        parent_lengths.append(length)
        if span:
            parents[(path, span[0], span[1])] = length

rows = []
seen = set()
for test in mini:
    if test["qid"] in seen:
        continue
    seen.add(test["qid"])
    blocks, context = 0, 0
    for i, span in enumerate(results[test["qid"]]["spans"][:TOP], 1):
        block = len(f"[{i}] ({span['file_path']})\n") + parents[(span["file_path"], *span["span"])]
        # Same test as rag.py: used is never incremented, so each block is compared to the cap alone.
        if block > CAP:
            break
        blocks += 1
        context += block + 2
    rows.append({"blocks": blocks, "context": context, "tokens": (context + 1400) / chars_per_token})

n = len(rows)
over = sum(1 for length in parent_lengths if length > CAP)
contexts = sorted(r["context"] for r in rows)
report = {
    "queries": n,
    "chunks": len(parent_lengths),
    "chunks_with_parent_over_cap": over,
    "share_chunks_with_parent_over_cap": round(over / len(parent_lengths), 4),
    "max_parent_chars": max(parent_lengths),
    "empty_context_queries": sum(r["blocks"] == 0 for r in rows),
    "partial_context_queries": sum(0 < r["blocks"] < TOP for r in rows),
    "full_context_queries": sum(r["blocks"] == TOP for r in rows),
    "context_chars_median": median(contexts),
    "context_chars_max": contexts[-1],
    "queries_over_cap_total": sum(r["context"] > CAP for r in rows),
    "chars_per_token_from_law_replay": round(chars_per_token, 2),
    "estimated_queries_over_num_ctx": sum(r["tokens"] > NUM_CTX for r in rows),
}
Path(__file__).with_suffix(".json").write_text(json.dumps(report, indent=1) + "\n")
print(json.dumps(report, indent=1))

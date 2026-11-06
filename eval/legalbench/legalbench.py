#!/usr/bin/env python3
"""Retrieval benchmark on LegalBench-RAG, scored with the benchmark's own code.

Subcommands: fetch, split, ingest, run, score. See README.md in this folder.
"""
from __future__ import annotations

import argparse
import asyncio
import hashlib
import io
import json
import platform
import random
import subprocess
import sys
import tarfile
import time
import uuid
import zipfile
from datetime import datetime, timezone
from pathlib import Path, PurePosixPath

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "backend" / "src"))

DATA = ROOT / "data" / "benchmarks" / "legalbench"
CORPUS = DATA / "data" / "corpus"
BENCHMARKS = DATA / "data" / "benchmarks"
VENDOR = DATA / "vendor"
RUNS = DATA / "runs"
CHUNKS = DATA / "chunks.jsonl"
SPLIT = Path(__file__).parent / "split.json"

DATASET_URL = (
    "https://www.dropbox.com/scl/fo/r7xfa5i3hdsbxex1w6amw/AID389Olvtm-ZLTKAPrw6k4"
    "?rlkey=5n8zrbk4c08lbit3iiexofmwg&st=0hu354cq&dl=1"
)
DATASET_SHA256 = "27431be37db9b1db23f8ab790a42d076adb1f72d7f9e7562e36a10573405f88d"
SCORER_COMMIT = "431bc8f2488a81569ab7259fa633dcc50ab77f9a"

SUBSETS = ("privacy_qa", "contractnli", "maud", "cuad")
# Same constants as the benchmark's benchmark.py; these define the 776-query mini set.
MAX_TESTS_PER_BENCHMARK = 194
KS = (1, 2, 4, 8, 16, 32, 64)
SPLIT_SEED = 20261106
DEV_DOC_FRACTION = 0.25
NAMESPACE = uuid.UUID("6f3d0a3e-52c1-4a7e-9d39-7b6c1f0e2a11")


def query_id(subset: str, test: dict) -> str:
    raw = f"{subset}|{test['query']}|{test['snippets'][0]['file_path']}|{test['snippets'][0]['span']}"
    return hashlib.sha256(raw.encode()).hexdigest()[:16]


def load_mini() -> list[dict]:
    """Reproduce the official mini selection (SORT_BY_DOCUMENT=True in benchmark.py)."""
    out: list[dict] = []
    for subset in SUBSETS:
        tests = json.loads((BENCHMARKS / f"{subset}.json").read_text())["tests"]
        if len(tests) > MAX_TESTS_PER_BENCHMARK:
            tests = sorted(
                tests,
                key=lambda t: (random.seed(t["snippets"][0]["file_path"]), random.random())[1],
            )[:MAX_TESTS_PER_BENCHMARK]
        for test in tests:
            out.append({**test, "subset": subset, "qid": query_id(subset, test)})
    return out


def locate_chunks(text: str, chunks: list[dict]) -> list[tuple[int, int] | None]:
    """Find each chunk's character span; the product chunker doesn't record offsets.

    Chunks arrive in document order but may overlap, so the search resumes just after the
    previous chunk's start. Resuming after its end sends repeated text to a later copy.
    """
    spans: list[tuple[int, int] | None] = []
    cursor = 0
    for chunk in chunks:
        content = chunk["content"]
        start = text.find(content, cursor)
        if start < 0:
            spans.append(None)
            continue
        spans.append((start, start + len(content)))
        cursor = start + 1
    return spans


def cmd_fetch(_args: argparse.Namespace) -> int:
    import httpx

    DATA.mkdir(parents=True, exist_ok=True)
    archive = DATA / "LegalBench-RAG.zip"
    if not archive.is_file():
        print("Downloading dataset...")
        with httpx.stream("GET", DATASET_URL, follow_redirects=True, timeout=600) as response:
            response.raise_for_status()
            with archive.open("wb") as fh:
                for block in response.iter_bytes():
                    fh.write(block)
    digest = hashlib.sha256(archive.read_bytes()).hexdigest()
    if digest != DATASET_SHA256:
        print(f"Checksum mismatch: {digest}", file=sys.stderr)
        return 1
    with zipfile.ZipFile(archive) as bundle:
        names = [n for n in bundle.namelist() if n != "/"]
        for name in names:
            if name.startswith("/") or ".." in PurePosixPath(name).parts:
                print(f"Unsafe path in archive: {name}", file=sys.stderr)
                return 1
        bundle.extractall(DATA / "data", members=names)

    url = f"https://github.com/zeroentropy-ai/legalbenchrag/archive/{SCORER_COMMIT}.tar.gz"
    response = httpx.get(url, follow_redirects=True, timeout=120)
    response.raise_for_status()
    VENDOR.mkdir(parents=True, exist_ok=True)
    with tarfile.open(fileobj=io.BytesIO(response.content)) as tar:
        tar.extractall(VENDOR, filter="data")
    print(f"Dataset and scorer ready in {DATA}")
    return 0


def cmd_split(_args: argparse.Namespace) -> int:
    """Split by document so tuning never sees text the test queries are about."""
    mini = load_mini()
    rng = random.Random(SPLIT_SEED)
    dev_docs: list[str] = []
    for subset in SUBSETS:
        docs = sorted({t["snippets"][0]["file_path"] for t in mini if t["subset"] == subset})
        rng.shuffle(docs)
        dev_docs.extend(docs[: max(1, round(len(docs) * DEV_DOC_FRACTION))])
    dev = set(dev_docs)
    assignment = {
        t["qid"]: "dev" if t["snippets"][0]["file_path"] in dev else "test" for t in mini
    }
    SPLIT.write_text(
        json.dumps(
            {
                "seed": SPLIT_SEED,
                "unit": "document of the query's first snippet",
                "dev_fraction_of_documents": DEV_DOC_FRACTION,
                "dev_documents": sorted(dev),
                "assignment": dict(sorted(assignment.items())),
            },
            indent=1,
        )
        + "\n"
    )
    for name in ("dev", "test"):
        counts = {
            s: sum(1 for t in mini if t["subset"] == s and assignment[t["qid"]] == name)
            for s in SUBSETS
        }
        print(name, sum(counts.values()), counts)
    return 0


async def _ingest() -> dict:
    from sqlalchemy import text

    from db import async_session_factory
    from services.advanced_chunking import hierarchical_chunk
    from services.contextual_retrieval import build_embedding_text
    from services.embeddings import embed_texts
    from services.vector_store import delete_by_document_id, insert_chunk

    docs = sorted({s["file_path"] for t in load_mini() for s in t["snippets"]})
    stats = {"documents": len(docs), "chunks": 0, "unlocated": 0, "chars": 0, "covered": 0}
    started = time.perf_counter()
    with CHUNKS.open("w", encoding="utf-8") as sink:
        async with async_session_factory() as db:
            for n, path in enumerate(docs, 1):
                body = (CORPUS / path).read_text()
                document_id = uuid.uuid5(NAMESPACE, path)
                items = hierarchical_chunk(body)
                spans = locate_chunks(body, items)
                # parent_content is left out: ranking never reads it, and in full it
                # adds 2.5 GB of duplicated text for this corpus.
                metas = [
                    {
                        "source": "contract",
                        "title": path,
                        "kind": "contract",
                        "document_id": str(document_id),
                        "confidentiality": "internal",
                        "parent_id": item.get("parent_id"),
                        "parent_title": item.get("parent_title"),
                        "child_index": item.get("child_index"),
                        "bench_span": list(span) if span else None,
                    }
                    for item, span in zip(items, spans)
                ]
                vectors = embed_texts(
                    [build_embedding_text(i["content"], m) for i, m in zip(items, metas)]
                )
                await delete_by_document_id(db, document_id)
                for index, (item, meta, vector) in enumerate(zip(items, metas, vectors)):
                    await insert_chunk(
                        db,
                        document_id=document_id,
                        chunk_index=index,
                        content=item["content"],
                        embedding=vector,
                        metadata=meta,
                    )
                    sink.write(
                        json.dumps(
                            {
                                "file_path": path,
                                "span": meta["bench_span"],
                                "content": item["content"],
                            }
                        )
                        + "\n"
                    )
                await db.commit()
                stats["chunks"] += len(items)
                stats["unlocated"] += sum(1 for s in spans if s is None)
                stats["chars"] += len(body)
                stats["covered"] += sum(s[1] - s[0] for s in spans if s)
                print(f"[{n}/{len(docs)}] {path}: {len(items)} chunks", flush=True)
            # Same index the law ingest creates, so vector search behaves as in the product.
            await db.execute(
                text(
                    "CREATE INDEX IF NOT EXISTS idx_document_chunks_embedding_hnsw "
                    "ON document_chunks USING hnsw (embedding vector_cosine_ops)"
                )
            )
            await db.commit()
    stats["seconds"] = round(time.perf_counter() - started, 1)
    return stats


def cmd_ingest(_args: argparse.Namespace) -> int:
    stats = asyncio.run(_ingest())
    (DATA / "ingest_stats.json").write_text(json.dumps(stats, indent=1))
    print(stats)
    return 1 if stats["unlocated"] else 0


def _spans_from_hits(hits: list[dict]) -> list[dict]:
    out = []
    for hit in hits:
        meta = hit.get("metadata") or {}
        if meta.get("bench_span"):
            out.append({"file_path": meta["title"], "span": meta["bench_span"]})
    return out


def _run_bm25(mini: list[dict]) -> dict[str, dict]:
    """External baseline: real Okapi BM25 on the same chunks as the product modes."""
    import bm25s

    rows = [json.loads(line) for line in CHUNKS.read_text(encoding="utf-8").splitlines()]
    index = bm25s.BM25()
    index.index(bm25s.tokenize([r["content"] for r in rows], stopwords="en", show_progress=False))
    tokens = bm25s.tokenize([t["query"] for t in mini], stopwords="en", show_progress=False)
    results, _scores = index.retrieve(tokens, k=max(KS), show_progress=False)
    return {
        test["qid"]: {
            "spans": [
                {"file_path": rows[i]["file_path"], "span": rows[i]["span"]}
                for i in results[n]
                if rows[i]["span"]
            ]
        }
        for n, test in enumerate(mini)
    }


async def _run_product_mode(mode: str, mini: list[dict]) -> dict[str, dict]:
    from sqlalchemy import text

    from config import settings
    from db import async_session_factory
    from services.embeddings import embed_texts
    from services.query_enhance import expand_legal_query
    from services.rag import _retrieve_and_rank
    from services.reranker import rerank
    from services.vector_store import hybrid_search, search_fts, search_similar

    docs = {uuid.uuid5(NAMESPACE, s["file_path"]) for t in mini for s in t["snippets"]}
    access = {
        "accessible_document_ids": docs,
        "include_law_corpus": False,
        "user_role": "owner",
    }
    top = max(KS)
    results: dict[str, dict] = {}
    vectors = (
        None
        if mode == "fts"
        else embed_texts([t["query"] for t in mini])
    )
    async with async_session_factory() as db:
        for n, test in enumerate(mini):
            query = test["query"]
            extra: dict = {}
            started = time.perf_counter()
            if mode == "fts":
                hits = await search_fts(db, expand_legal_query(query), top_k=top, **access)
            elif mode == "dense":
                hits = await search_similar(db, vectors[n], top_k=top, **access)
            elif mode == "dense_exact":
                await db.execute(text("SET LOCAL enable_indexscan = off"))
                hits = await search_similar(db, vectors[n], top_k=top, **access)
                await db.rollback()
            elif mode == "hybrid":
                hits = await hybrid_search(
                    db, expand_legal_query(query), vectors[n], top_k=top, **access
                )
            elif mode == "hybrid_rerank":
                pool = await hybrid_search(
                    db, expand_legal_query(query), vectors[n], top_k=top, **access
                )
                hits = rerank(query, pool, top_k=top)
            elif mode == "product":
                # Unmodified pipeline: default pool of 20, reranked; k above 20 can't improve.
                settings.rag_rerank_k = settings.rag_top_k
                hits = await _retrieve_and_rank(
                    db,
                    query,
                    accessible_ids=docs,
                    include_law=False,
                    user_role="owner",
                    doc_uuid=None,
                    use_hyde=False,
                )
                extra["top_rerank_score"] = hits[0].get("rerank_score") if hits else None
            else:
                raise ValueError(mode)
            results[test["qid"]] = {
                "spans": _spans_from_hits(hits),
                "returned": len(hits),
                "seconds": round(time.perf_counter() - started, 4),
                **extra,
            }
            if (n + 1) % 100 == 0:
                print(f"  {mode}: {n + 1}/{len(mini)}", flush=True)
    return results


async def _run_product_modes(modes: list[str], mini: list[dict], out: Path) -> None:
    # One event loop for all modes: the engine's pooled connections belong to the loop that made them.
    for mode in modes:
        print(f"== {mode}", flush=True)
        results = await _run_product_mode(mode, mini)
        (out / f"{mode}.json").write_text(json.dumps(results))


def cmd_run(args: argparse.Namespace) -> int:
    mini = load_mini()
    out = RUNS / args.run
    out.mkdir(parents=True, exist_ok=True)
    modes = args.modes.split(",")
    if "bm25" in modes:
        (out / "bm25.json").write_text(json.dumps(_run_bm25(mini)))
    product_modes = [mode for mode in modes if mode != "bm25"]
    if product_modes:
        asyncio.run(_run_product_modes(product_modes, mini, out))
    return 0


def _commit() -> str:
    try:
        return subprocess.check_output(
            ["git", "-C", str(ROOT), "rev-parse", "HEAD"], text=True
        ).strip()
    except (OSError, subprocess.CalledProcessError):
        return "unknown"


def _hardware() -> str:
    try:
        gpu = subprocess.check_output(
            ["nvidia-smi", "--query-gpu=name,memory.total", "--format=csv,noheader"], text=True
        ).strip()
    except (OSError, subprocess.CalledProcessError):
        gpu = "no GPU"
    return f"{platform.machine()}, {gpu}"


def _interval(values: list[float], *, seed: int = 7, rounds: int = 1000) -> list[float]:
    rng = random.Random(seed)
    n = len(values)
    means = sorted(sum(rng.choices(values, k=n)) / n for _ in range(rounds))
    return [round(means[int(rounds * 0.025)], 4), round(means[int(rounds * 0.975)], 4)]


def _score_group(tests: list[dict], results: dict, k: int) -> dict:
    sys.path.insert(0, str(VENDOR / f"legalbenchrag-{SCORER_COMMIT}"))
    from legalbenchrag.benchmark_types import QAGroundTruth, RetrievedSnippet
    from legalbenchrag.run_benchmark import QAResult

    recalls: list[float] = []
    precisions: list[float] = []
    for test in tests:
        truth = QAGroundTruth(query=test["query"], snippets=test["snippets"], tags=[test["subset"]])
        spans = results.get(test["qid"], {}).get("spans", [])[:k]
        scored = QAResult(
            qa_gt=truth,
            retrieved_snippets=[
                RetrievedSnippet(file_path=s["file_path"], span=tuple(s["span"]), score=0.0)
                for s in spans
            ],
        )
        recalls.append(scored.recall)
        precisions.append(scored.precision)
    return {
        "n": len(tests),
        "recall": round(sum(recalls) / len(recalls), 4),
        "recall_ci95": _interval(recalls),
        "precision": round(sum(precisions) / len(precisions), 4),
        "precision_ci95": _interval(precisions),
    }


def cmd_score(args: argparse.Namespace) -> int:
    """Score one split. Writes aggregates only, so test failures stay unread."""
    mini = load_mini()
    assignment = json.loads(SPLIT.read_text())["assignment"]
    tests = [t for t in mini if assignment[t["qid"]] == args.split]
    run_dir = RUNS / args.run
    report: dict = {
        "benchmark": "LegalBench-RAG mini (official selection)",
        "scorer_commit": SCORER_COMMIT,
        "dataset_sha256": DATASET_SHA256,
        "code_commit": _commit(),
        "split": args.split,
        "split_seed": SPLIT_SEED,
        "run": args.run,
        "date": datetime.now(timezone.utc).isoformat(),
        "hardware": _hardware(),
        "embedding_model": "bge-m3",
        "reranker_model": "ms-marco cross-encoder (data/models/reranker)",
        "note": args.note,
        "modes": {},
    }
    for path in sorted(run_dir.glob("*.json")):
        results = json.loads(path.read_text())
        mode: dict = {"by_k": {}}
        for k in KS:
            entry = {"all": _score_group(tests, results, k)}
            for subset in SUBSETS:
                entry[subset] = _score_group([t for t in tests if t["subset"] == subset], results, k)
            mode["by_k"][str(k)] = entry
        returned = [results[t["qid"]]["returned"] for t in tests if "returned" in results.get(t["qid"], {})]
        seconds = sorted(results[t["qid"]]["seconds"] for t in tests if "seconds" in results.get(t["qid"], {}))
        if returned:
            mode["returned_rows"] = {
                "min": min(returned),
                "mean": round(sum(returned) / len(returned), 2),
                "zero_rows": sum(1 for r in returned if r == 0),
                "max": max(returned),
            }
        if seconds:
            mode["seconds"] = {
                "p50": seconds[len(seconds) // 2],
                "p95": seconds[int(len(seconds) * 0.95)],
            }
        report["modes"][path.stem] = mode
    target = Path(args.output)
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps(report, indent=1) + "\n")

    lines = [
        f"Split: {args.split} (n={len(tests)}); run: {args.run}",
        f"Commit: {report['code_commit'][:7]}; date: {report['date'][:10]}; hardware: {report['hardware']}",
        f"Embeddings: {report['embedding_model']}; reranker: {report['reranker_model']}",
        "",
    ]
    lines.append("| Mode | " + " | ".join(f"R@{k}" for k in KS) + " | " + " | ".join(f"P@{k}" for k in (1, 8, 64)) + " |")
    lines.append("|---|" + "---|" * (len(KS) + 3))
    for name, mode in report["modes"].items():
        recall = [f"{mode['by_k'][str(k)]['all']['recall'] * 100:.1f}" for k in KS]
        precision = [f"{mode['by_k'][str(k)]['all']['precision'] * 100:.1f}" for k in (1, 8, 64)]
        lines.append(f"| {name} | " + " | ".join(recall + precision) + " |")
    table = "\n".join(lines) + "\n"
    target.with_suffix(".md").write_text(table)
    print(table)
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("fetch").set_defaults(func=cmd_fetch)
    sub.add_parser("split").set_defaults(func=cmd_split)
    sub.add_parser("ingest").set_defaults(func=cmd_ingest)
    run = sub.add_parser("run")
    run.add_argument("--run", required=True)
    run.add_argument("--modes", default="fts,dense,dense_exact,hybrid,hybrid_rerank,product")
    run.set_defaults(func=cmd_run)
    score = sub.add_parser("score")
    score.add_argument("--run", required=True)
    score.add_argument("--split", choices=("dev", "test"), required=True)
    score.add_argument("--output", required=True)
    score.add_argument("--note", default="")
    score.set_defaults(func=cmd_score)
    args = parser.parse_args()
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())

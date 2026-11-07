#!/usr/bin/env python3
"""Compare local models as JurisGuard's generator, on the same prompts the product builds.

  compare.py prompts --set bench    (ML image, juris_bench): 30 seeded LegalBench dev questions with retrieved context
  compare.py prompts --set german   (ML image, juris_db): German BDSG questions, the project's own, regression only
  compare.py generate --model M     (host): answers, speed and GPU share, with the product's Ollama options
  compare.py json --model M         (host): rate of valid structured output for clause extraction
  compare.py judge --model M        (host): RAGAS faithfulness and answer relevancy, judged by another model

Everything except the model is held fixed, so differences come from the model. Answers skip the product's checks
after generation, such as the extractive fallback.
"""
from __future__ import annotations

import argparse
import asyncio
import json
import random
import statistics
import sys
import time
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
# Prompts and answers hold benchmark text, which isn't committed, so only the summary goes in reports.
RAW = ROOT / "data" / "benchmarks" / "models"
OUT = ROOT / "eval" / "reports" / "models"
OLLAMA = "http://localhost:11434"
SEED = 20261107
QUESTIONS = 30
JUDGE = "llama3.1:8b"
# The product's generation options (services.ollama_client._generation_options with OLLAMA_NUM_GPU=99).
OPTIONS = {"temperature": 0.1, "num_predict": 1024, "num_ctx": 4096, "num_gpu": 99, "use_mmap": False}
GERMAN_QUESTIONS = [
    "Wann darf ein Arbeitgeber Daten von Beschäftigten verarbeiten?",
    "Wann muss ein Datenschutzbeauftragter benannt werden?",
    "Unter welchen Voraussetzungen ist Videoüberwachung öffentlich zugänglicher Räume zulässig?",
    "Welche Rechte hat die betroffene Person auf Auskunft nach dem BDSG?",
    "Welche Bußgelder sieht das Bundesdatenschutzgesetz vor?",
    "Darf eine Behörde besondere Kategorien personenbezogener Daten verarbeiten?",
    "Wann dürfen personenbezogene Daten für wissenschaftliche Forschung verarbeitet werden?",
    "Welche Aufgaben hat die oder der Bundesbeauftragte für den Datenschutz?",
]
CLAUSE_SCHEMA = {
    "type": "object",
    "properties": {
        "clause_present": {"type": "boolean"},
        "clause_type": {"type": "string"},
        "quote": {"type": "string"},
    },
    "required": ["clause_present", "clause_type", "quote"],
}


def _post(path: str, body: dict, timeout: float = 600) -> dict:
    request = urllib.request.Request(OLLAMA + path, json.dumps(body).encode(), {"Content-Type": "application/json"})
    with urllib.request.urlopen(request, timeout=timeout) as response:
        return json.load(response)


def _thinks(model: str) -> bool:
    return "thinking" in _post("/api/show", {"model": model}).get("capabilities", [])


def _system_prompt() -> str:
    sys.path.insert(0, str(ROOT / "backend" / "src"))
    from services.llm_client import SYSTEM_PROMPT

    return SYSTEM_PROMPT


async def _bench_prompts() -> list[dict]:
    sys.path.insert(0, str(ROOT / "eval" / "legalbench"))
    import legalbench as lb

    from db import async_session_factory
    from services.rag import _format_context, _retrieve_and_rank

    assignment = json.loads(lb.SPLIT.read_text())["assignment"]
    dev = sorted((t for t in lb.load_mini() if assignment[t["qid"]] == "dev"), key=lambda t: t["qid"])
    sample = random.Random(SEED).sample(dev, QUESTIONS)
    documents = {lb.uuid.uuid5(lb.NAMESPACE, s["file_path"]) for t in lb.load_mini() for s in t["snippets"]}
    out = []
    async with async_session_factory() as db:
        for test in sample:
            ranked = await _retrieve_and_rank(
                db, test["query"], accessible_ids=documents, include_law=False, user_role="owner", doc_uuid=None, use_hyde=False
            )
            context, sources = _format_context(ranked)
            out.append({"qid": test["qid"], "subset": test["subset"], "question": test["query"], "context": context,
                        "contexts": [s["content"] for s in sources]})
    return out


async def _german_prompts() -> list[dict]:
    from db import async_session_factory
    from services.rag import _format_context, _retrieve_and_rank

    out = []
    async with async_session_factory() as db:
        for n, question in enumerate(GERMAN_QUESTIONS):
            ranked = await _retrieve_and_rank(
                db, question, accessible_ids=None, include_law=True, user_role="owner", doc_uuid=None, use_hyde=False
            )
            context, sources = _format_context(ranked)
            out.append({"qid": f"de-{n}", "subset": "german", "question": question, "context": context,
                        "contexts": [s["content"] for s in sources]})
    return out


def cmd_prompts(args: argparse.Namespace) -> int:
    RAW.mkdir(parents=True, exist_ok=True)
    prompts = asyncio.run(_bench_prompts() if args.set == "bench" else _german_prompts())
    (RAW / f"prompts_{args.set}{args.tag}.json").write_text(json.dumps(prompts, indent=1, ensure_ascii=False))
    print(f"{len(prompts)} prompts saved")
    return 0


def _stream_answer(model: str, messages: list[dict], think: bool | None) -> dict:
    body = {"model": model, "messages": messages, "stream": True, "keep_alive": "10m", "options": OPTIONS}
    if think is not None:
        body["think"] = think
    request = urllib.request.Request(OLLAMA + "/api/chat", json.dumps(body).encode(), {"Content-Type": "application/json"})
    started = time.perf_counter()
    first = None
    text = []
    with urllib.request.urlopen(request, timeout=600) as response:
        for line in response:
            data = json.loads(line)
            piece = (data.get("message") or {}).get("content") or ""
            if piece and first is None:
                first = time.perf_counter() - started
            text.append(piece)
            if data.get("done"):
                return {
                    "answer": "".join(text).strip(),
                    "first_token_s": first,
                    "total_s": time.perf_counter() - started,
                    "tokens": data.get("eval_count"),
                    "tokens_per_s": data["eval_count"] / (data["eval_duration"] / 1e9) if data.get("eval_duration") else None,
                    "prompt_tokens": data.get("prompt_eval_count"),
                    "done_reason": data.get("done_reason"),
                }
    raise RuntimeError("stream ended without a final message")


def _gpu_share(model: str) -> float:
    with urllib.request.urlopen(OLLAMA + "/api/ps") as response:
        entry = next(m for m in json.load(response)["models"] if m["model"] == model)
    return entry["size_vram"] / entry["size"]


def cmd_generate(args: argparse.Namespace) -> int:
    system = _system_prompt()
    think = False if _thinks(args.model) else None
    _post("/api/chat", {"model": args.model, "messages": [{"role": "user", "content": "ok"}], "stream": False,
                        "keep_alive": "10m", "options": {**OPTIONS, "num_predict": 1}, **({"think": think} if think is not None else {})})
    share = _gpu_share(args.model)
    rows = []
    for name in ("bench", "german"):
        for prompt in json.loads((RAW / f"prompts_{name}{args.tag if name == 'bench' else ''}.json").read_text()):
            messages = [{"role": "system", "content": f"{system}\n\nContext:\n{prompt['context']}"},
                        {"role": "user", "content": prompt["question"]}]
            rows.append({**{k: prompt[k] for k in ("qid", "subset", "question", "contexts")}, "set": name,
                         **_stream_answer(args.model, messages, think)})
            print(f"  {args.model} {len(rows)}: {rows[-1]['total_s']:.1f}s", flush=True)
    share_after = _gpu_share(args.model)
    _write(args.model + args.tag, "answers", {"model": args.model, "gpu_share_start": share, "gpu_share_end": share_after,
                                   "think_disabled": think is False, "rows": rows})
    return 0


def _clause_prompt(context: str) -> str:
    return (
        "From the contract text below, report whether it contains a confidentiality clause. Reply with JSON only: "
        '{"clause_present": true or false, "clause_type": "<short label>", "quote": "<exact sentence from the text, '
        'or empty>"}.\n\nContract text:\n' + context
    )


def cmd_json(args: argparse.Namespace) -> int:
    think = False if _thinks(args.model) else None
    prompts = json.loads((RAW / "prompts_bench.json").read_text())
    results = []
    for prompt in prompts:
        body = {"model": args.model, "messages": [{"role": "user", "content": _clause_prompt(prompt["context"])}],
                "stream": False, "format": CLAUSE_SCHEMA, "keep_alive": "10m", "options": OPTIONS}
        if think is not None:
            body["think"] = think
        reply = _post("/api/chat", body)["message"]["content"]
        try:
            parsed = json.loads(reply)
            valid = isinstance(parsed.get("clause_present"), bool) and isinstance(parsed.get("clause_type"), str) and isinstance(parsed.get("quote"), str)
            quote = parsed.get("quote", "").strip()
            grounded = valid and (not quote or quote in prompt["context"])
        except (json.JSONDecodeError, AttributeError):
            valid = grounded = False
        results.append({"qid": prompt["qid"], "valid": valid, "quote_in_text": grounded})
    _write(args.model, "json", {"model": args.model, "valid_rate": sum(r["valid"] for r in results) / len(results),
                                "quote_in_text_rate": sum(r["quote_in_text"] for r in results) / len(results),
                                "rows": results})
    return 0


def cmd_judge(args: argparse.Namespace) -> int:
    sys.path.insert(0, str(ROOT / "scripts"))
    from run_native_ragas import judge_rows, summarise

    from check_llm_gpu import gpu_share

    answers = json.loads(_path(args.model + args.tag, "answers").read_text())
    if args.model == JUDGE:
        raise SystemExit("The judge can't grade itself")
    share = gpu_share(JUDGE, {"num_predict": 1, "num_ctx": 8192, "num_gpu": 99, "use_mmap": False}, keep_alive="5m")
    if share < 1.0:
        raise SystemExit(f"Judge {JUDGE} is only {share:.0%} on the GPU")
    rows = [{"qid": r["qid"], "subset": r["subset"], "query": r["question"], "answer": r["answer"], "contexts": r["contexts"]}
            for r in answers["rows"] if r["set"] == "bench" and r["answer"]]
    import run_native_ragas

    run_native_ragas.DEFAULT_JUDGE = JUDGE
    per_row = judge_rows(rows, JUDGE, 99)
    _write(args.model + args.tag, "judged", {"model": args.model, "judge": JUDGE, "metrics": summarise(per_row), "per_query": per_row})
    return 0


def _path(model: str, kind: str) -> Path:
    folder = RAW if kind == "answers" else OUT
    return folder / f"{model.replace(':', '_').replace('/', '_')}_{kind}.json"


def _write(model: str, kind: str, data: dict) -> None:
    _path(model, kind).parent.mkdir(parents=True, exist_ok=True)
    _path(model, kind).write_text(json.dumps(data, indent=1, ensure_ascii=False))


def cmd_table(_args: argparse.Namespace) -> int:
    sys.path.insert(0, str(ROOT / "backend" / "src"))
    from services.rag import looks_german

    lines = ["| Model | GPU | First token p50 | Answer p50 / p95 | Tokens/s | Faithfulness | Relevancy | Valid JSON | German replies |",
             "|---|---|---|---|---|---|---|---|---|"]
    for answers_file in sorted(RAW.glob("*_answers.json")):
        answers = json.loads(answers_file.read_text())
        model = answers_file.name.removesuffix("_answers.json")
        bench = [r for r in answers["rows"] if r["set"] == "bench"]
        german = [r for r in answers["rows"] if r["set"] == "german"]
        totals = sorted(r["total_s"] for r in bench)
        judged_file, json_file = OUT / f"{model}_judged.json", OUT / f"{model}_json.json"
        judged = json.loads(judged_file.read_text())["metrics"] if judged_file.exists() else {}
        valid = json.loads(json_file.read_text())["valid_rate"] if json_file.exists() else None
        fmt = lambda v: f"{v:.2f}" if isinstance(v, float) else "n/a"  # noqa: E731
        lines.append(
            f"| {model} | {min(answers['gpu_share_start'], answers['gpu_share_end']):.0%} "
            f"| {statistics.median(r['first_token_s'] for r in bench):.2f} s "
            f"| {statistics.median(totals):.1f} / {totals[int(0.95 * (len(totals) - 1))]:.1f} s "
            f"| {statistics.median(r['tokens_per_s'] for r in bench):.0f} "
            f"| {fmt(judged.get('faithfulness'))} | {fmt(judged.get('answer_relevancy'))} "
            f"| {'n/a' if valid is None else f'{valid:.0%}'} "
            f"| {sum(looks_german(r['answer']) for r in german)}/{len(german)} |"
        )
    (OUT / "comparison.md").write_text("\n".join(lines) + "\n")
    print("\n".join(lines))
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)
    # --tag keeps a variant's files apart, for example prompts built with a different number of chunks.
    p = sub.add_parser("prompts"); p.add_argument("--set", choices=("bench", "german"), required=True)
    p.add_argument("--tag", default=""); p.set_defaults(func=cmd_prompts)
    for name, func in (("generate", cmd_generate), ("json", cmd_json), ("judge", cmd_judge)):
        c = sub.add_parser(name); c.add_argument("--model", required=True); c.add_argument("--tag", default="")
        c.set_defaults(func=func)
    sub.add_parser("table").set_defaults(func=cmd_table)
    args = parser.parse_args()
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())

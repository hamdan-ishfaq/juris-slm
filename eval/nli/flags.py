#!/usr/bin/env python3
"""Can a flag on unsupported claims fire rarely on supported ones and still catch contradictions? (eval/nli/PREREGISTRATION.md)

Each ContractNLI hypothesis stands in for a claim in an answer; the premise is the five contract spans closest to it by
bge-m3, as retrieval would supply them. Every option gives a support score; a claim is flagged when the score is below a
threshold chosen on dev so that 10% of supported claims are flagged.

  concat-base   mDeBERTa-v3-base (xnli), entailment probability with the five spans joined, as in D-014
  span-base     the same model on each span alone, highest entailment probability
  span-small    multilingual MiniLM-L6 on each span alone, highest entailment probability
  qwen-judge    Qwen3 8B, the product's generator, asked for a JSON verdict; flagged unless "supported" (no threshold)

  flags.py score --split dev        (ML image; saves raw scores under data/benchmarks/contractnli/)
  flags.py score --split heldout    (once: 200 pairs per label drawn from ContractNLI train, seed 20261114)
  flags.py table                    (thresholds from dev, applied once to heldout; writes the report)
"""
from __future__ import annotations

import argparse
import asyncio
import json
import math
import random
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "grounding"))
import contractnli as cn  # noqa: E402

RAW = cn.RAW
OUT = cn.ROOT / "eval" / "reports" / "nli_flags_2026-11"
SEED = 20261114
PER_LABEL = 200
FALSE_FLAG_TARGET = 0.10
OPTIONS = ("concat-base", "span-base", "span-small", "qwen-judge")
LABELS = ("Entailment", "Contradiction", "NotMentioned")
JUDGE_SCHEMA = {
    "type": "object",
    "properties": {"verdict": {"type": "string", "enum": ["supported", "contradicted", "not_mentioned"]}},
    "required": ["verdict"],
}


def heldout_pairs() -> list[dict]:
    """200 pairs per label from the train split, which no earlier run in the project used."""
    rows = cn.pairs("train")
    rng = random.Random(SEED)
    out = []
    for label in LABELS:
        group = [r for r in rows if r["label"] == label]
        out.extend(rng.sample(group, PER_LABEL))
    return out


def _span_max(name: str, rows: list[dict]) -> tuple[list[float], float]:
    import torch
    from transformers import AutoModelForSequenceClassification, AutoTokenizer

    path = cn.ROOT / "data" / "models" / "nli" / cn.NLI_MODELS[name][0].split("/")[1]
    tokenizer = AutoTokenizer.from_pretrained(path)
    model = AutoModelForSequenceClassification.from_pretrained(path).eval()
    entailment = next(i for i, label in model.config.id2label.items() if label.lower().startswith("entail"))
    scores = []
    started = time.perf_counter()
    with torch.inference_mode():
        for row in rows:
            premises = [row["spans"][i] for i in row["retrieved"]]
            encoded = tokenizer(premises, [row["hypothesis"]] * len(premises), truncation="only_first", max_length=512,
                                padding=True, return_tensors="pt")
            scores.append(float(torch.softmax(model(**encoded).logits, dim=-1)[:, entailment].max()))
    return scores, (time.perf_counter() - started) * 1000 / max(len(rows), 1)


async def _judge(rows: list[dict]) -> tuple[list[float], list[str], float]:
    from config import settings
    from services.ollama_client import chat_with_model

    verdicts = []
    started = time.perf_counter()
    for n, row in enumerate(rows, 1):
        text = "\n\n".join(f"[{k}] {row['spans'][i]}" for k, i in enumerate(row["retrieved"], 1))
        messages = [
            {"role": "system", "content": "You check claims against contract text. Use only the text given."},
            {"role": "user", "content": f"Contract text:\n{text}\n\nClaim: {row['hypothesis']}\n\n"
                                        "Does the text support the claim, contradict it, or not mention it?"},
        ]
        try:
            reply = await chat_with_model(messages, model=settings.ollama_model, json_schema=JUDGE_SCHEMA)
            verdicts.append(json.loads(reply)["verdict"])
        except Exception as exc:  # a failed call counts as not supported, and is recorded
            verdicts.append(f"error: {str(exc)[:80]}")
        if n % 100 == 0:
            print(f"  judge {n}/{len(rows)}", flush=True)
    ms = (time.perf_counter() - started) * 1000 / max(len(rows), 1)
    return [1.0 if v == "supported" else 0.0 for v in verdicts], verdicts, ms


def cmd_score(args: argparse.Namespace) -> int:
    rows = cn.pairs("dev") if args.split == "dev" else heldout_pairs()
    cn._contexts(rows)
    result = {"split": args.split, "pairs": len(rows), "labels": [r["label"] for r in rows], "scores": {}, "ms_per_claim": {}}
    for option in args.options.split(","):
        print(f"== {option}", flush=True)
        if option == "concat-base":
            scores, ms = cn._nli_scores("nli-base", rows, "retrieved")
        elif option == "span-base":
            scores, ms = _span_max("nli-base", rows)
        elif option == "span-small":
            scores, ms = _span_max("nli-small", rows)
        else:
            scores, verdicts, ms = asyncio.run(_judge(rows))
            result["judge_verdicts"] = verdicts
        result["scores"][option] = scores
        result["ms_per_claim"][option] = round(ms, 1)
        print(f"  {option}: {ms:.0f} ms per claim", flush=True)
    target = RAW / f"flags_{args.split}.json"
    if target.exists():  # several invocations (CPU options, then the judge) fill one file
        old = json.loads(target.read_text())
        old["scores"].update(result["scores"])
        old["ms_per_claim"].update(result["ms_per_claim"])
        old.update({k: v for k, v in result.items() if k == "judge_verdicts"})
        result = old
    target.write_text(json.dumps(result))
    return 0


def _wilson(k: int, n: int) -> list[float]:
    if not n:
        return [0.0, 0.0]
    p, z = k / n, 1.96
    centre = (p + z * z / (2 * n)) / (1 + z * z / n)
    half = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / (1 + z * z / n)
    return [round(max(0.0, centre - half), 4), round(min(1.0, centre + half), 4)]


def _rate(labels: list[str], flagged: list[bool], label: str) -> dict:
    hits = [f for lab, f in zip(labels, flagged) if lab == label]
    return {"rate": round(sum(hits) / len(hits), 4), "ci95": _wilson(sum(hits), len(hits)), "n": len(hits)}


def _threshold(dev: dict, option: str) -> float | None:
    """The score below which 10% of dev's supported claims fall; the judge has no threshold."""
    if option == "qwen-judge":
        return None
    supported = sorted(s for s, lab in zip(dev["scores"][option], dev["labels"]) if lab == "Entailment")
    return supported[int(FALSE_FLAG_TARGET * len(supported))]


def cmd_table(_args: argparse.Namespace) -> int:
    dev = json.loads((RAW / "flags_dev.json").read_text())
    held = json.loads((RAW / "flags_heldout.json").read_text())
    report = {"false_flag_target_on_dev": FALSE_FLAG_TARGET, "options": {}}
    lines = [
        "| Option | Threshold (dev) | False flags on supported | Contradicted flagged | Not mentioned flagged | ms per claim (CPU or GPU) | Passes rule 1-2 |",
        "|---|---|---|---|---|---|---|",
    ]
    for option in OPTIONS:
        if option not in held["scores"] or option not in dev["scores"]:
            continue
        t = _threshold(dev, option)
        flag = (lambda s: s < t) if t is not None else (lambda s: s < 0.5)
        flagged = [flag(s) for s in held["scores"][option]]
        ff = _rate(held["labels"], flagged, "Entailment")
        con = _rate(held["labels"], flagged, "Contradiction")
        nm = _rate(held["labels"], flagged, "NotMentioned")
        dev_ff = _rate(dev["labels"], [flag(s) for s in dev["scores"][option]], "Entailment")["rate"]
        passes = ff["ci95"][1] <= 0.15 and con["rate"] >= 0.30 and con["ci95"][0] > ff["rate"]
        report["options"][option] = {"threshold": t, "dev_false_flags": dev_ff, "false_flags": ff, "contradicted": con,
                                     "not_mentioned": nm, "ms_per_claim": held["ms_per_claim"][option], "passes_rules_1_2": passes}
        fmt = lambda r: f"{r['rate'] * 100:.1f}% [{r['ci95'][0] * 100:.1f}, {r['ci95'][1] * 100:.1f}]"
        lines.append(f"| {option} | {'—' if t is None else f'{t:.3f}'} (dev false flags {dev_ff * 100:.1f}%) | {fmt(ff)} | "
                     f"{fmt(con)} | {fmt(nm)} | {held['ms_per_claim'][option]:.0f} | {'yes' if passes else 'no'} |")
    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / "heldout.json").write_text(json.dumps(report, indent=1) + "\n")
    (OUT / "heldout.md").write_text("\n".join(lines) + "\n")
    print("\n".join(lines))
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = parser.add_subparsers(dest="command", required=True)
    score = sub.add_parser("score")
    score.add_argument("--split", choices=("dev", "heldout"), required=True)
    score.add_argument("--options", default=",".join(OPTIONS))
    score.set_defaults(func=cmd_score)
    sub.add_parser("table").set_defaults(func=cmd_table)
    args = parser.parse_args()
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())

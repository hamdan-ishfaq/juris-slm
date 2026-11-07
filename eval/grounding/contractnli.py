#!/usr/bin/env python3
"""Can the answer check tell a claim the contract supports from one it contradicts or never mentions? Measured on ContractNLI.

Each ContractNLI hypothesis stands in for an answer, and the check decides whether the contract text supports it. Two settings:

  gold       the annotated evidence spans as the context; Entailment should pass and Contradiction fail. This isolates the check.
  retrieved  the five spans closest to the hypothesis by bge-m3, as retrieval would supply them; only Entailment should pass.

Checks compared:

  current        the product's _answer_uses_context, unchanged: cosine to a span >= 0.55 or six shared content words
  cosine         the same cosine score with a threshold tuned on dev
  nli-base       MoritzLaurer/mDeBERTa-v3-base-xnli-multilingual-nli-2mil7, entailment probability, threshold tuned on dev
  nli-small      MoritzLaurer/multilingual-MiniLMv2-L6-mnli-xnli, the same

ContractNLI is English, so German is not tested here. The product embeds chunks with the document name in front; spans here are
embedded as they are.

  contractnli.py score --split dev      (ML image; saves every score)
  contractnli.py score --split test     (once, after the thresholds are fixed from dev)
  contractnli.py table                  (thresholds from dev, applied to test)
"""
from __future__ import annotations

import argparse
import json
import random
import sys
import time
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "backend" / "src"))
DATA = ROOT / "data" / "benchmarks" / "contractnli" / "contract-nli"
RAW = ROOT / "data" / "benchmarks" / "contractnli"
OUT = ROOT / "eval" / "reports" / "grounding_2026-11"
TOP_SPANS = 5
NLI_MODELS = {
    "nli-base": ("MoritzLaurer/mDeBERTa-v3-base-xnli-multilingual-nli-2mil7", "b5113eb38ab63efdd7f280f8c144ea8b13f978ce"),
    "nli-small": ("MoritzLaurer/multilingual-MiniLMv2-L6-mnli-xnli", "0a71e92a985b6e1ad1828cf67ce9c459639c1dca"),
}
CHECKS = ("current", "cosine", *NLI_MODELS)


def pairs(split: str) -> list[dict]:
    data = json.loads((DATA / f"{split}.json").read_text())
    out = []
    for doc in data["documents"]:
        spans = [doc["text"][start:end].strip() for start, end in doc["spans"]]
        for key, annotation in doc["annotation_sets"][0]["annotations"].items():
            out.append({
                "doc": doc["id"],
                "spans": spans,
                "hypothesis": data["labels"][key]["hypothesis"],
                "label": annotation["choice"],
                "evidence": sorted(annotation["spans"]),
            })
    return out


def _unit(matrix: np.ndarray) -> np.ndarray:
    return matrix / np.linalg.norm(matrix, axis=1, keepdims=True)


def _contexts(rows: list[dict]) -> None:
    """Add the gold and retrieved span indices to each row, embedding every span once per document."""
    from services.embeddings import embed_texts

    by_doc: dict[str, list[dict]] = {}
    for row in rows:
        by_doc.setdefault(row["doc"], []).append(row)
    for n, group in enumerate(by_doc.values(), 1):
        spans = group[0]["spans"]
        span_vectors = _unit(np.asarray(embed_texts(spans)))
        hypothesis_vectors = _unit(np.asarray(embed_texts([row["hypothesis"] for row in group])))
        for row, vector in zip(group, hypothesis_vectors):
            sims = span_vectors @ vector
            row["retrieved"] = sorted(int(i) for i in np.argsort(-sims)[:TOP_SPANS])
            row["span_vectors"] = span_vectors
        print(f"  embedded document {n}/{len(by_doc)}", flush=True)


def _current_scores(rows: list[dict], setting: str) -> tuple[list[float], list[bool], float]:
    """The product's check as it ships, and its cosine score for a tuned threshold."""
    from services.embeddings import embed_texts
    from services.rag import _answer_uses_context

    cosines, verdicts = [], []
    started = time.perf_counter()
    for row in rows:
        indices = row[setting]
        context = "\n\n".join(row["spans"][i] for i in indices)
        vectors = [row["span_vectors"][i] for i in indices]
        verdicts.append(bool(_answer_uses_context(row["hypothesis"], context, chunk_vectors=vectors)))
        answer = _unit(np.asarray(embed_texts([row["hypothesis"][:1500]])))[0]
        cosines.append(float(max(np.asarray(vectors) @ answer)))
    per_check_ms = (time.perf_counter() - started) * 1000 / max(len(rows), 1) / 2  # two embeddings per row, one per check
    return cosines, verdicts, per_check_ms


def _nli_scores(name: str, rows: list[dict], setting: str) -> tuple[list[float], float]:
    import torch
    from transformers import AutoModelForSequenceClassification, AutoTokenizer

    path = ROOT / "data" / "models" / "nli" / NLI_MODELS[name][0].split("/")[1]
    tokenizer = AutoTokenizer.from_pretrained(path)
    model = AutoModelForSequenceClassification.from_pretrained(path).eval()
    entailment = next(i for i, label in model.config.id2label.items() if label.lower().startswith("entail"))
    scores: list[float] = []
    started = time.perf_counter()
    with torch.inference_mode():
        for start in range(0, len(rows), 8):
            batch = rows[start:start + 8]
            premises = [" ".join(row["spans"][i] for i in row[setting]) for row in batch]
            encoded = tokenizer(premises, [row["hypothesis"] for row in batch], truncation="only_first", max_length=512,
                                padding=True, return_tensors="pt")
            probabilities = torch.softmax(model(**encoded).logits, dim=-1)[:, entailment]
            scores.extend(float(p) for p in probabilities)
    return scores, (time.perf_counter() - started) * 1000 / max(len(rows), 1)


def cmd_score(args: argparse.Namespace) -> int:
    rows = pairs(args.split)
    _contexts(rows)
    result: dict = {"split": args.split, "top_spans": TOP_SPANS, "models": NLI_MODELS, "settings": {}}
    for setting in ("gold", "retrieved"):
        chosen = [r for r in rows if r["evidence"] and r["label"] != "NotMentioned"] if setting == "gold" else rows
        for row in chosen:
            row["gold"] = row["evidence"]
        cosines, verdicts, current_ms = _current_scores(chosen, setting)
        entry = {"labels": [r["label"] for r in chosen], "cosine": cosines, "current": verdicts,
                 "ms_per_check": {"current": round(current_ms, 1)}}
        for name in NLI_MODELS:
            entry[name], ms = _nli_scores(name, chosen, setting)
            entry["ms_per_check"][name] = round(ms, 1)
        result["settings"][setting] = entry
        print(f"  {setting}: {len(chosen)} pairs, ms per check {entry['ms_per_check']}", flush=True)
    RAW.mkdir(parents=True, exist_ok=True)
    (RAW / f"scores_{args.split}.json").write_text(json.dumps(result))
    return 0


def _passes(entry: dict, check: str, threshold: float | None) -> list[bool]:
    if check == "current":
        return entry["current"]
    return [score >= threshold for score in entry[check]]


def _balanced(labels: list[str], passed: list[bool]) -> float:
    supported = [p for label, p in zip(labels, passed) if label == "Entailment"]
    unsupported = [not p for label, p in zip(labels, passed) if label != "Entailment"]
    return (sum(supported) / len(supported) + sum(unsupported) / len(unsupported)) / 2


def _interval(labels: list[str], passed: list[bool], rounds: int = 1000) -> list[float]:
    rng = random.Random(7)
    indices = range(len(labels))
    values = []
    for _ in range(rounds):
        sample = rng.choices(indices, k=len(labels))
        values.append(_balanced([labels[i] for i in sample], [passed[i] for i in sample]))
    values.sort()
    return [round(values[25], 3), round(values[974], 3)]


def _tune(entry: dict, check: str) -> float:
    """The threshold with the best balanced accuracy on dev."""
    candidates = sorted(set(round(s, 3) for s in entry[check]))
    return max(candidates, key=lambda t: _balanced(entry["labels"], _passes(entry, check, t)))


def cmd_table(_args: argparse.Namespace) -> int:
    dev = json.loads((RAW / "scores_dev.json").read_text())["settings"]
    test = json.loads((RAW / "scores_test.json").read_text())["settings"]
    report: dict = {"benchmark": "ContractNLI (CC BY 4.0), test split", "top_spans": TOP_SPANS, "models": NLI_MODELS,
                    "threshold_from": "dev, retrieved setting, best balanced accuracy", "settings": {}}
    thresholds = {check: None if check == "current" else _tune(dev["retrieved"], check) for check in CHECKS}
    lines = ["| Setting | Check | Threshold | Supported passed | Contradicted passed | Not mentioned passed | Balanced accuracy | ms per check |",
             "|---|---|---|---|---|---|---|---|"]
    for setting in ("gold", "retrieved"):
        entry = test[setting]
        report["settings"][setting] = {}
        for check in CHECKS:
            passed = _passes(entry, check, thresholds[check])
            rates = {}
            for label in ("Entailment", "Contradiction", "NotMentioned"):
                chosen = [p for lab, p in zip(entry["labels"], passed) if lab == label]
                rates[label] = round(sum(chosen) / len(chosen), 3) if chosen else None
            balanced = round(_balanced(entry["labels"], passed), 3)
            ms = entry["ms_per_check"].get(check, entry["ms_per_check"]["current"])
            report["settings"][setting][check] = {
                "threshold": thresholds[check], "pass_rate": rates, "n": {lab: entry["labels"].count(lab) for lab in rates},
                "balanced_accuracy": balanced, "balanced_accuracy_ci95": _interval(entry["labels"], passed), "ms_per_check": ms,
            }
            shown = "product" if thresholds[check] is None else thresholds[check]
            nm = "n/a" if rates["NotMentioned"] is None else f"{rates['NotMentioned']:.1%}"
            lines.append(f"| {setting} | {check} | {shown} | {rates['Entailment']:.1%} | {rates['Contradiction']:.1%} | {nm} | "
                         f"{balanced:.3f} {report['settings'][setting][check]['balanced_accuracy_ci95']} | {ms} |")
    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / "contractnli_check.json").write_text(json.dumps(report, indent=1) + "\n")
    (OUT / "contractnli_check.md").write_text("\n".join(lines) + "\n")
    print("\n".join(lines))
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = parser.add_subparsers(dest="command", required=True)
    score = sub.add_parser("score")
    score.add_argument("--split", choices=("dev", "test"), required=True)
    score.set_defaults(func=cmd_score)
    sub.add_parser("table").set_defaults(func=cmd_table)
    args = parser.parse_args()
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())

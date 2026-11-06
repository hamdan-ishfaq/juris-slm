#!/usr/bin/env python3
"""
Phase 1.1 — Convert raw datasets to instruction-tuning JSONL.

Usage (from v2/, one dataset at a time recommended):
  python scripts/02_prepare_training_data.py --list
  python scripts/02_prepare_training_data.py --only cuad
  python scripts/02_prepare_training_data.py --only contract_nli
  python scripts/02_prepare_training_data.py --only ledgar
  python scripts/02_prepare_training_data.py --only maud
  python scripts/02_prepare_training_data.py --all

Output: data/processed/{source}_pairs.jsonl
"""
from __future__ import annotations

import argparse
import sys
from typing import Any, Callable

from datasets import load_from_disk
from tqdm import tqdm

from training_common import PROCESSED, RAW, ensure_processed_dir, truncate, write_jsonl

Pair = dict[str, str]


def _base_pair(instruction: str, inp: str, output: str, source: str) -> Pair:
    return {
        "instruction": instruction.strip(),
        "input": truncate(inp),
        "output": output.strip(),
        "source": source,
    }


# ---------------------------------------------------------------------------
# CUAD
# ---------------------------------------------------------------------------

CUAD_INSTRUCTION = """You are a legal contract analyst specializing in commercial agreements.
Given the contract excerpt and question, identify the relevant clause text and summarize:
1) whether the clause type is present,
2) the key obligation or value,
3) any risk flags for review."""


def prepare_cuad() -> list[Pair]:
    path = RAW / "cuad"
    if not path.is_dir():
        raise FileNotFoundError(f"CUAD not found at {path}. Run download first.")

    ds_dict = load_from_disk(str(path))
    pairs: list[Pair] = []

    for split_name, split in ds_dict.items():
        for row in tqdm(split, desc=f"CUAD/{split_name}", unit="ex"):
            answers = row.get("answers") or []
            if isinstance(answers, str):
                answers = [answers]
            answer_text = "; ".join(a for a in answers if a).strip()
            if not answer_text and row.get("is_impossible"):
                answer_text = "No relevant clause found in this excerpt."
            elif not answer_text:
                continue

            question = row.get("question", "")
            context = row.get("context") or row.get("title", "")
            inp = f"Contract excerpt:\n{context}\n\nQuestion: {question}"

            pairs.append(_base_pair(CUAD_INSTRUCTION, inp, answer_text, "cuad"))

    return pairs


# ---------------------------------------------------------------------------
# ContractNLI
# ---------------------------------------------------------------------------

CONTRACT_NLI_INSTRUCTION = """You are a legal contract analyst.
Given a contract clause and a legal claim, reason step by step then give a verdict:
Entailment, Contradiction, Neutral, or Not mentioned."""

LABEL_MAP = {
    "entailment": "Entailment",
    "contradiction": "Contradiction",
    "neutral": "Neutral",
    "notmentioned": "Not mentioned",
    "not_mentioned": "Not mentioned",
}


def _normalize_nli_label(label: Any) -> str:
    if label is None:
        return "Neutral"
    s = str(label).strip().lower()
    return LABEL_MAP.get(s, s.title())


def prepare_contract_nli() -> list[Pair]:
    path = RAW / "contract_nli"
    if not path.is_dir():
        raise FileNotFoundError(f"ContractNLI not found at {path}")

    ds_dict = load_from_disk(str(path))
    pairs: list[Pair] = []

    for split_name, split in ds_dict.items():
        for row in tqdm(split, desc=f"ContractNLI/{split_name}", unit="ex"):
            clause = row.get("text") or row.get("premise") or ""
            claim = row.get("hypothesis") or ""
            label = _normalize_nli_label(row.get("label"))

            inp = f"Contract clause:\n{clause}\n\nLegal claim:\n{claim}"
            output = (
                f"Step 1 — Read the clause and identify what it requires or permits.\n"
                f"Step 2 — Compare the claim against the clause scope.\n"
                f"Step 3 — Note gaps, exceptions, or conflicts.\n"
                f"Verdict: {label}"
            )
            pairs.append(_base_pair(CONTRACT_NLI_INSTRUCTION, inp, output, "contract_nli"))

    return pairs


# ---------------------------------------------------------------------------
# LEDGAR
# ---------------------------------------------------------------------------

LEDGAR_INSTRUCTION = """You are a legal contract analyst.
Classify the following contract provision into its primary provision category.
Name the category and briefly explain why this text belongs to that category."""


def prepare_ledgar() -> list[Pair]:
    path = RAW / "ledgar"
    if not path.is_dir():
        raise FileNotFoundError(f"LEDGAR not found at {path}")

    ds_dict = load_from_disk(str(path))
    pairs: list[Pair] = []

    for split_name, split in ds_dict.items():
        for row in tqdm(split, desc=f"LEDGAR/{split_name}", unit="ex"):
            text = row.get("text") or row.get("content") or ""
            label = row.get("label")
            if label is None:
                continue
            label_name = str(label).replace("_", " ").strip()
            if not text.strip():
                continue

            output = (
                f"Provision category: {label_name}\n"
                f"Reasoning: This provision primarily addresses {label_name.lower()} based on its language and structure."
            )
            pairs.append(_base_pair(LEDGAR_INSTRUCTION, text, output, "ledgar"))

    return pairs


# ---------------------------------------------------------------------------
# MAUD
# ---------------------------------------------------------------------------

MAUD_INSTRUCTION = """You are an M&A legal analyst reviewing merger agreement clauses.
Answer the deal-point question using only the provided clause text.
Reason briefly, then state the expert answer."""


def prepare_maud() -> list[Pair]:
    path = RAW / "maud"
    if not path.is_dir():
        raise FileNotFoundError(f"MAUD not found at {path}")

    ds_dict = load_from_disk(str(path))
    pairs: list[Pair] = []

    for split_name, split in ds_dict.items():
        for row in tqdm(split, desc=f"MAUD/{split_name}", unit="ex"):
            text = row.get("text") or ""
            question = row.get("question") or ""
            answer = row.get("answer") or row.get("answers") or ""
            category = row.get("category") or row.get("deal_point_category") or ""

            if not text.strip() or not question.strip():
                continue
            if not str(answer).strip():
                continue

            inp = (
                f"Deal category: {category}\n\n"
                f"Clause text:\n{text}\n\n"
                f"Question: {question}"
            )
            output = (
                f"Step 1 — Locate the language in the clause relevant to the question.\n"
                f"Step 2 — Apply M&A deal-point interpretation.\n"
                f"Answer: {answer}"
            )
            pairs.append(_base_pair(MAUD_INSTRUCTION, inp, output, "maud"))

    return pairs


# ---------------------------------------------------------------------------
# Runner
# ---------------------------------------------------------------------------

PREPARERS: dict[str, tuple[str, Callable[[], list[Pair]]]] = {
    "cuad": ("CUAD", prepare_cuad),
    "contract_nli": ("ContractNLI", prepare_contract_nli),
    "ledgar": ("LEDGAR", prepare_ledgar),
    "maud": ("MAUD", prepare_maud),
}


def main() -> int:
    parser = argparse.ArgumentParser(description="Prepare instruction-tuning JSONL from raw datasets")
    parser.add_argument("--list", action="store_true")
    parser.add_argument("--all", action="store_true")
    parser.add_argument("--only", help="Single source: cuad, contract_nli, ledgar, maud")
    args = parser.parse_args()

    if args.list:
        for key, (label, _) in PREPARERS.items():
            out = PROCESSED / f"{key}_pairs.jsonl"
            print(f"  {key:16} → {out}")
        return 0

    if args.all:
        keys = list(PREPARERS.keys())
    elif args.only:
        if args.only not in PREPARERS:
            print(f"Unknown source: {args.only}. Use --list.", file=sys.stderr)
            return 1
        keys = [args.only]
    else:
        parser.print_help()
        return 0

    ensure_processed_dir()
    errors: list[str] = []

    for key in keys:
        label, fn = PREPARERS[key]
        out = PROCESSED / f"{key}_pairs.jsonl"
        print(f"\n{'='*60}\n  Preparing {label} → {out}\n{'='*60}")
        try:
            pairs = fn()
            write_jsonl(out, pairs)
            print(f"✓ {key}: {len(pairs):,} examples → {out}")
        except Exception as exc:
            errors.append(f"{key}: {exc}")
            print(f"✗ {key} FAILED: {exc}", file=sys.stderr)

    if errors:
        print(f"\nFinished with {len(errors)} error(s).", file=sys.stderr)
        return 1
    print("\nPhase 1.1 complete. Next: python scripts/04_build_final_dataset.py")
    return 0


if __name__ == "__main__":
    sys.exit(main())

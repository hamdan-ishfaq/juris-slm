#!/usr/bin/env python3
"""
Phase 1.3 (OPTIONAL) — Generate synthetic CoT examples using local Ollama.

Requires: ollama installed + phi3.5 pulled
This step takes hours — skip until Ollama is set up.

Usage:
  python scripts/03_generate_synthetic.py --max-examples 100   # small test
  python scripts/03_generate_synthetic.py --max-examples 3000 # overnight
"""
from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path

import requests
from datasets import load_from_disk
from tqdm import tqdm

from training_common import PROCESSED, RAW, ensure_processed_dir, truncate, write_jsonl

OLLAMA_URL = "http://localhost:11434/api/generate"
MODEL = "phi3.5"

TEACHER_PROMPT = """You are a senior legal analyst specializing in commercial contracts under German and EU law.

Analyze this contract clause and respond in this exact format:

CLAUSE TYPE: [category]
PARTIES BOUND: [parties or N/A]
KEY OBLIGATIONS: [numbered list]
CONDITIONS & EXCEPTIONS: [list or None]
RISK LEVEL: [Low/Medium/High]
RISK RATIONALE: [one sentence]

Contract clause:
{clause}"""


def ollama_available() -> bool:
    try:
        r = requests.get("http://localhost:11434/api/tags", timeout=3)
        return r.status_code == 200
    except requests.RequestException:
        return False


def generate_one(clause: str, timeout: int = 120) -> str:
    resp = requests.post(
        OLLAMA_URL,
        json={
            "model": MODEL,
            "prompt": TEACHER_PROMPT.format(clause=truncate(clause, 1200)),
            "stream": False,
            "options": {"temperature": 0.1, "num_predict": 400},
        },
        timeout=timeout,
    )
    resp.raise_for_status()
    return resp.json().get("response", "").strip()


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--max-examples", type=int, default=100)
    parser.add_argument("--source", default="cuad", choices=["cuad"])
    args = parser.parse_args()

    if not ollama_available():
        print(
            "Ollama not running. Install and start:\n"
            "  curl -fsSL https://ollama.com/install.sh | sh\n"
            "  ollama pull phi3.5\n"
            "  ollama serve\n"
            "Skip this step for now — synthetic data is optional.",
            file=sys.stderr,
        )
        return 1

    cuad_path = RAW / "cuad"
    if not cuad_path.is_dir():
        print("CUAD not found. Run dataset download + 02_prepare first.", file=sys.stderr)
        return 1

    ds = load_from_disk(str(cuad_path))
    split = ds["train"] if "train" in ds else ds[list(ds.keys())[0]]

    clauses: list[str] = []
    for row in split:
        ans = row.get("answers") or []
        if isinstance(ans, list) and ans:
            for a in ans:
                if a and len(a) > 50:
                    clauses.append(a)
        elif row.get("context"):
            clauses.append(row["context"])
        if len(clauses) >= args.max_examples:
            break

    clauses = clauses[: args.max_examples]
    ensure_processed_dir()
    out = PROCESSED / "synthetic_pairs.jsonl"
    existing = []
    if out.exists():
        with out.open(encoding="utf-8") as f:
            for line in f:
                if line.strip():
                    existing.append(json.loads(line))
        print(f"Resuming: {len(existing)} existing synthetic examples")

    pairs = existing
    start = len(pairs)

    for i, clause in enumerate(tqdm(clauses[start:], desc="Synthetic (Ollama)", unit="ex")):
        try:
            analysis = generate_one(clause)
            pairs.append(
                {
                    "instruction": "Perform a structured legal analysis of this contract clause.",
                    "input": truncate(clause, 1200),
                    "output": analysis,
                    "source": "synthetic",
                }
            )
            if (i + 1) % 10 == 0:
                write_jsonl(out, pairs)  # checkpoint
        except Exception as exc:
            print(f"\n  Warning at example {start + i}: {exc}", file=sys.stderr)
            time.sleep(5)
            continue

    write_jsonl(out, pairs)
    print(f"\n✓ {len(pairs):,} synthetic examples → {out}")
    print("Re-run: python scripts/04_build_final_dataset.py to include synthetic data")
    return 0


if __name__ == "__main__":
    sys.exit(main())

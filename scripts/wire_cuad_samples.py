#!/usr/bin/env python3
"""Index a small CUAD/LEDGAR sample into eval fixtures for contract retrieval tests."""
from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
RAW = ROOT / "data" / "raw"
OUT = ROOT / "eval" / "fixtures" / "cuad_samples.jsonl"


def _load_hf_json(name: str, limit: int = 20) -> list[dict]:
    path = RAW / name
    if not path.is_dir():
        return []
    for candidate in sorted(path.rglob("*.json"))[:3]:
        try:
            data = json.loads(candidate.read_text(encoding="utf-8"))
            if isinstance(data, list):
                return data[:limit]
        except (json.JSONDecodeError, OSError):
            continue
    return []


def main() -> int:
    samples: list[dict] = []
    for ds in ("cuad", "ledgar"):
        rows = _load_hf_json(ds, limit=10)
        for row in rows:
            text = row.get("context") or row.get("text") or row.get("content") or ""
            if not text:
                continue
            samples.append({"dataset": ds, "text": text[:4000]})
    OUT.parent.mkdir(parents=True, exist_ok=True)
    with OUT.open("w", encoding="utf-8") as fh:
        for s in samples:
            fh.write(json.dumps(s, ensure_ascii=False) + "\n")
    print(f"Wrote {len(samples)} samples to {OUT}")
    return 0 if samples else 0


if __name__ == "__main__":
    raise SystemExit(main())

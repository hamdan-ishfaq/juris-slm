"""Shared helpers for Phase 1 training data preparation."""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Iterator

from tqdm import tqdm

ROOT = Path(__file__).resolve().parents[1]
RAW = ROOT / "data" / "raw"
PROCESSED = ROOT / "data" / "processed"


def ensure_processed_dir() -> Path:
    PROCESSED.mkdir(parents=True, exist_ok=True)
    return PROCESSED


def write_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as f:
        for row in rows:
            f.write(json.dumps(row, ensure_ascii=False) + "\n")


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    with path.open(encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                rows.append(json.loads(line))
    return rows


def iter_jsonl(path: Path) -> Iterator[dict[str, Any]]:
    with path.open(encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                yield json.loads(line)


def count_jsonl_lines(path: Path) -> int:
    if not path.exists():
        return 0
    n = 0
    with path.open(encoding="utf-8") as f:
        for _ in f:
            n += 1
    return n


def truncate(text: str, max_chars: int = 2000) -> str:
    text = (text or "").strip()
    if len(text) <= max_chars:
        return text
    return text[: max_chars - 3].rstrip() + "..."

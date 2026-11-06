#!/usr/bin/env python3
"""Ingest law corpus (no bash — avoids CRLF issues on WSL)."""
from __future__ import annotations

import asyncio
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend" / "src"))

os.environ.setdefault(
    "DATABASE_URL",
    "postgresql+asyncpg://juris:juris_password@localhost:5433/juris_db",
)
os.environ.setdefault("EMBEDDING_MODEL_PATH", str(ROOT / "data" / "models" / "bge-m3"))
os.environ.setdefault("RERANKER_MODEL_PATH", str(ROOT / "data" / "models" / "reranker"))
os.environ.setdefault("LAW_CORPUS_PATH", str(ROOT / "data" / "raw" / "law_corpus"))


def main() -> int:
    import argparse

    parser = argparse.ArgumentParser(description="Ingest law corpus")
    parser.add_argument("--force", action="store_true", help="Re-ingest even if corpus exists")
    args = parser.parse_args()

    bge = Path(os.environ["EMBEDDING_MODEL_PATH"])
    if not bge.is_dir():
        print(f"Missing {bge} — run: python scripts/download_assets.py --models --only bge-m3")
        return 1
    weights = list(bge.rglob("*.safetensors")) + list(bge.rglob("pytorch_model.bin"))
    print(f"bge-m3 weights found: {len(weights)} file(s)")
    if not weights:
        print("Re-download: python scripts/download_assets.py --models --only bge-m3 --force")
        return 1

    from ingest_law import main as ingest_main

    asyncio.run(ingest_main(force=args.force))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

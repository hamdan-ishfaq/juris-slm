#!/usr/bin/env python3
"""Verify downloaded datasets and models (cross-platform, no bash CRLF issues)."""
from __future__ import annotations

import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
RAW = ROOT / "data" / "raw"
MODELS = ROOT / "data" / "models"


def check_dir(name: str, path: Path, min_files: int = 1) -> bool:
    if path.is_dir() and len(list(path.rglob("*"))) >= min_files:
        files = [f for f in path.rglob("*") if f.is_file()]
        if len(files) >= min_files:
            print(f"  [OK]   {name}")
            return True
    print(f"  [MISS] {name} → {path}")
    return False


def check_file(name: str, path: Path, min_bytes: int = 500) -> bool:
    if path.is_file() and path.stat().st_size > min_bytes:
        print(f"  [OK]   {name}")
        return True
    print(f"  [MISS] {name} → {path}")
    return False


def main() -> int:
    ok = 0
    fail = 0

    print("=" * 40)
    print(" Phase 0.3 — Datasets")
    print("=" * 40)

    checks = [
        ("CUAD", lambda: check_dir("CUAD", RAW / "cuad", 3)),
        ("LEDGAR", lambda: check_dir("LEDGAR", RAW / "ledgar", 3)),
        ("ContractNLI", lambda: check_dir("ContractNLI", RAW / "contract_nli", 3)),
        ("MAUD", lambda: check_dir("MAUD", RAW / "maud", 3)),
        ("BGB (EN)", lambda: check_file("BGB (EN)", RAW / "law_corpus" / "bgb_en.txt")),
        ("GDPR (EN)", lambda: check_file("GDPR (EN)", RAW / "law_corpus" / "gdpr_en.txt")),
    ]
    for _, fn in checks:
        if fn():
            ok += 1
        else:
            fail += 1

    print()
    print("=" * 40)
    print(" Phase 0.4 — Models")
    print("=" * 40)

    def check_model_weights(name: str, path: Path, min_weight_bytes: int) -> bool:
        if not path.is_dir():
            print(f"  [MISS] {name} → {path}")
            return False
        weights = list(path.rglob("*.safetensors")) + list(path.rglob("pytorch_model.bin"))
        big = [f for f in weights if f.is_file() and f.stat().st_size >= min_weight_bytes]
        if big:
            print(f"  [OK]   {name} ({big[0].name}, {big[0].stat().st_size // 1_000_000} MB)")
            return True
        print(f"  [MISS] {name} — no weight file ≥ {min_weight_bytes // 1_000_000}MB in {path}")
        return False

    if check_model_weights("bge-m3", MODELS / "bge-m3", 500_000_000):
        ok += 1
    else:
        fail += 1
    if check_model_weights("reranker", MODELS / "reranker", 10_000_000):
        ok += 1
    else:
        fail += 1

    if shutil.which("ollama"):
        try:
            out = subprocess.check_output(["ollama", "list"], text=True, stderr=subprocess.DEVNULL)
            if "phi3.5" in out.lower():
                print("  [OK]   phi3.5 (Ollama)")
                ok += 1
            else:
                print("  [MISS] phi3.5 (Ollama) — run: ollama pull phi3.5")
                fail += 1
        except subprocess.CalledProcessError:
            print("  [SKIP] ollama list failed")
    else:
        print("  [SKIP] ollama CLI not installed")

    print()
    print(f" Results: {ok} OK, {fail} missing")

    if fail == 0:
        print("Phase 0.3/0.4 COMPLETE")
        return 0

    print("Run: python scripts/download_assets.py --all")
    return 1


if __name__ == "__main__":
    sys.exit(main())

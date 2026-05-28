#!/usr/bin/env python3
"""Pin ML stack inside running API container (no bash / CRLF issues)."""
from __future__ import annotations

import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

# bge-m3 uses pytorch_model.bin — transformers 4.48+ needs torch>=2.6 for torch.load
TORCH = "2.6.0"
ST = "3.4.1"
TRANSFORMERS = "4.49.0"
TOKENIZERS = "0.21.4"

VERIFY = """
import torch, sentence_transformers, transformers
print("torch", torch.__version__)
print("sentence_transformers", sentence_transformers.__version__)
print("transformers", transformers.__version__)
from sentence_transformers import SentenceTransformer
m = SentenceTransformer("/app/data/models/bge-m3", device="cpu", trust_remote_code=True)
v = m.encode(["smoke test"], normalize_embeddings=True)
print("bge-m3 encode ok, dim=", len(v[0]))
"""


def run(cmd: list[str], *, check: bool = True) -> subprocess.CompletedProcess:
    print("+", " ".join(cmd))
    return subprocess.run(cmd, cwd=ROOT, check=check)


def pip(*args: str, check: bool = True) -> None:
    run(["docker", "compose", "exec", "-T", "api", "pip", *args], check=check)


def main() -> int:
    print("Removing old ML packages from api container...")
    pip("uninstall", "-y", "sentence-transformers", "transformers", "tokenizers", check=False)

    print("Installing CPU torch", TORCH, "...")
    pip(
        "install",
        "-q",
        f"torch=={TORCH}",
        "--index-url",
        "https://download.pytorch.org/whl/cpu",
    )

    print("Installing pinned sentence-transformers + transformers...")
    pip(
        "install",
        "-q",
        f"sentence-transformers=={ST}",
        f"transformers=={TRANSFORMERS}",
        f"tokenizers=={TOKENIZERS}",
    )

    print("Smoke test: load bge-m3 inside container...")
    proc = run(
        ["docker", "compose", "exec", "-T", "api", "python", "-c", VERIFY.strip()],
        check=False,
    )
    if proc.returncode != 0:
        print("ERROR: bge-m3 failed to load in container. See output above.", file=sys.stderr)
        return 1

    run(["docker", "compose", "restart", "api"])
    print("Done. Wait ~20s then: curl -s http://localhost:8002/health")
    print("Then: python scripts/00_verify_phase23.py")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

#!/usr/bin/env python3
"""Start v2 stack (no bash CRLF issues)."""
from __future__ import annotations

import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def run(*args: str) -> None:
    subprocess.run(args, cwd=ROOT, check=True)


def main() -> int:
    run("docker", "compose", "up", "-d", "db", "cache", "ollama")
    print("Waiting for db/cache...")
    time.sleep(5)
    run("docker", "compose", "up", "-d", "api")
    print("Stack started. Check: docker compose ps")
    print("Then: python scripts/ensure_docker_ml_deps.py")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

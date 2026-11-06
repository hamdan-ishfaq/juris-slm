#!/usr/bin/env python3
"""
Overnight model downloads with retries and logging.

Usage:
  nohup python scripts/download_overnight.py > data/nohup.out 2>&1 &

Environment:
  DOWNLOAD_MAX_RETRIES=20   (default)
  HF_TOKEN in v2/.env       (optional, faster downloads)
"""
from __future__ import annotations

import os
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
LOG = ROOT / "data" / "download_overnight.log"
PYTHON = ROOT / ".venv" / "bin" / "python"
if not PYTHON.exists():
    PYTHON = Path(sys.executable)


def log(msg: str) -> None:
    line = msg.rstrip()
    print(line, flush=True)
    LOG.parent.mkdir(parents=True, exist_ok=True)
    with LOG.open("a", encoding="utf-8") as f:
        f.write(line + "\n")


def run(cmd: list[str]) -> int:
    log(f"$ {' '.join(cmd)}")
    proc = subprocess.run(cmd, cwd=str(ROOT))
    return proc.returncode


def main() -> int:
    os.environ.setdefault("DOWNLOAD_MAX_RETRIES", "20")
    os.environ.setdefault("DOWNLOAD_RETRY_DELAY", "10")
    os.environ.setdefault("DOWNLOAD_RETRY_MAX_DELAY", "300")

    ts = datetime.now(timezone.utc).astimezone().isoformat(timespec="seconds")
    log("")
    log(f"=== JurisGuard overnight download started {ts} ===")
    log(f"Retries: {os.environ['DOWNLOAD_MAX_RETRIES']} | Log: {LOG}")
    log("")
    log("WARNING: If your laptop sleeps, downloads STOP.")
    log("  Windows: Settings → Power → Plugged in → Sleep = Never")
    log("  Keep plugged in; prefer lid open.")
    log("")

    dl_rc = run(
        [
            str(PYTHON),
            "scripts/download_assets.py",
            "--models",
            "--only",
            "bge-m3,reranker,phi35-tokenizer",
        ]
    )

    log("")
    log("=== Verify ===")
    verify_rc = run([str(PYTHON), "scripts/verify_assets.py"])

    end = datetime.now(timezone.utc).astimezone().isoformat(timespec="seconds")
    log("")
    log(f"=== Finished {end} download_exit={dl_rc} verify_exit={verify_rc} ===")

    if dl_rc == 0 and verify_rc == 0:
        log("SUCCESS — all models ready")
        return 0
    return 1


if __name__ == "__main__":
    sys.exit(main())

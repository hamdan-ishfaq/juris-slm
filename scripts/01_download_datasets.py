#!/usr/bin/env python3
"""Wrapper — forwards to download_assets.py --datasets."""
from __future__ import annotations

import subprocess
import sys
from pathlib import Path

if __name__ == "__main__":
    script = Path(__file__).parent / "download_assets.py"
    cmd = [sys.executable, str(script), "--datasets", *sys.argv[1:]]
    raise SystemExit(subprocess.call(cmd))

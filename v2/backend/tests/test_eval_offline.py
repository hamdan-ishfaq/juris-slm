"""Offline Phase 3 logical eval checks (no API required)."""
from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

V2_ROOT = Path(__file__).resolve().parents[2]


def test_logical_eval_offline_passes():
    script = V2_ROOT / "scripts" / "run_logical_eval.py"
    r = subprocess.run(
        [sys.executable, str(script), "--offline"],
        cwd=V2_ROOT,
        capture_output=True,
        text=True,
        timeout=60,
    )
    assert r.returncode == 0, r.stdout + r.stderr


def test_baseline_json_valid():
    path = V2_ROOT / "eval" / "baseline.json"
    data = json.loads(path.read_text(encoding="utf-8"))
    assert data.get("phase") in ("phase-3-eval", "masterpiece-eval")
    assert "ragas" in data
    assert "logical" in data
    assert data["logical"].get("pass_rate_min", 0) >= 0.93

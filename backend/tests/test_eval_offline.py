"""Offline Phase 3 logical eval checks (no API required)."""
from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

V2_ROOT = Path(__file__).resolve().parents[2]


def test_logical_eval_offline_passes(tmp_path):
    script = V2_ROOT / "scripts" / "run_logical_eval.py"
    r = subprocess.run(
        [sys.executable, str(script), "--offline", "--report", str(tmp_path / "logical.json")],
        cwd=V2_ROOT,
        capture_output=True,
        text=True,
        timeout=60,
    )
    assert r.returncode == 0, r.stdout + r.stderr


def test_baseline_json_valid():
    path = V2_ROOT / "eval" / "baseline.json"
    data = json.loads(path.read_text(encoding="utf-8"))
    assert data["context_proxy"]["context_gold_recall_proxy_min"] > 0
    assert data["retrieval_gate"]["hit_rate_min"] > 0
    # Measured 102 of 110. Raise this as results improve, so a floor can't drift down unnoticed.
    assert data["logical"]["pass_rate_min"] >= 0.90
    assert data["logical"]["api_airgap_target"]["pass_rate_min"] >= 0.90

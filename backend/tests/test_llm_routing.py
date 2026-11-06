"""Multi-tier LLM routing tests."""
from __future__ import annotations

import sys
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from config import Settings
import services.llm_client as llm_client_module
from services.llm_client import llm_profile, model_tiers_status


def test_dev_profile():
    cfg = Settings.model_validate({"LLM_PROVIDER": "openrouter", "OPENROUTER_API_KEY": "test-key"})
    with patch.object(llm_client_module, "settings", cfg):
        assert llm_profile() == "dev"


def test_airgap_profile():
    cfg = Settings.model_validate({"LLM_PROVIDER": "ollama"})
    with patch.object(llm_client_module, "settings", cfg):
        assert llm_profile() == "airgap"


def test_model_tiers_structure():
    tiers = model_tiers_status()
    assert "generation" in tiers
    assert "aux" in tiers

"""Eval substring matching tests."""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "scripts"))

from eval_common import substring_hit


def test_uk_us_minimisation():
    assert substring_hit("data minimization under Art. 5", ["minimisation"])


def test_transparency_variant():
    assert substring_hit("transparency obligations under Art. 12", ["transparent"])


def test_legal_obligation_variant():
    text = "processing necessary for compliance with a legal obligation under Art. 6"
    assert substring_hit(text, ["legal obligation", "Art. 6"])


def test_requires_all_substrings():
    assert not substring_hit("legal obligation only", ["legal obligation", "Art. 6"])


def test_article_six_variant():
    assert substring_hit("lawful basis under Article 6(1)(c)", ["Art. 6"])


def test_generic_article_variant():
    assert substring_hit("conditions under Article 7 GDPR", ["Art. 7"])
    assert not substring_hit("Article 8 only", ["Art. 7"])

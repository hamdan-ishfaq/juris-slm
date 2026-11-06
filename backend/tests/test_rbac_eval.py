"""Automated runner for eval/rbac.jsonl — Phase 1."""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from services.access_control import can_access_confidentiality, can_upload_confidentiality, matter_role_at_least

EVAL_PATH = Path(__file__).resolve().parents[2] / "eval" / "rbac.jsonl"


def _load_cases() -> list[dict]:
    cases = []
    for line in EVAL_PATH.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if line:
            cases.append(json.loads(line))
    return cases


@pytest.mark.parametrize(
    "case",
    [c for c in _load_cases() if "target_doc_confidentiality" in c],
    ids=lambda c: c.get("id", "?"),
)
def test_rbac_jsonl_confidentiality_matrix(case):
    actor = case.get("actor", "member")
    conf = case["target_doc_confidentiality"]
    expect = case.get("expect_chunks", 0)
    allowed = can_access_confidentiality(actor, conf)
    if expect == 0:
        assert not allowed
    elif expect == ">0":
        assert allowed


@pytest.mark.parametrize(
    "case",
    [c for c in _load_cases() if c.get("matter_member_role")],
    ids=lambda c: c.get("id", "?"),
)
def test_rbac_jsonl_matter_roles(case):
    role = case["matter_member_role"]
    if case.get("expect_upload") is False:
        assert not matter_role_at_least(role, "editor")
    elif case.get("expect_upload") is True:
        assert matter_role_at_least(role, "editor")

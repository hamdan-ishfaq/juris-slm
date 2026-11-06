"""Validate Phase 3 golden dataset integrity."""
from __future__ import annotations

import json
from pathlib import Path

import pytest

GOLDEN = Path(__file__).resolve().parents[2] / "eval" / "golden"


def _load(name: str) -> list[dict]:
    path = GOLDEN / name
    assert path.is_file(), f"missing {name}"
    rows = []
    for line in path.read_text(encoding="utf-8").splitlines():
        if line.strip():
            rows.append(json.loads(line))
    return rows


def test_golden_file_counts():
    assert len(_load("law_qa.jsonl")) == 50
    assert len(_load("contract_qa.jsonl")) == 20
    assert len(_load("injection.jsonl")) == 15
    assert len(_load("rbac.jsonl")) == 10


def test_golden_unique_ids():
    ids: set[str] = set()
    for fname in ("law_qa.jsonl", "contract_qa.jsonl", "injection.jsonl", "rbac.jsonl"):
        for row in _load(fname):
            rid = row["id"]
            assert rid not in ids, f"duplicate id {rid}"
            ids.add(rid)
    assert len(ids) == 95


def test_law_qa_schema():
    for row in _load("law_qa.jsonl"):
        assert "question" in row
        assert "id" in row
        if not row.get("expect_refusal"):
            assert row.get("gold_chunk_substrings") or row.get("gold_articles")


def test_injection_schema():
    for row in _load("injection.jsonl"):
        assert row.get("expect_status") == 400 or row.get("expect_safe_refusal")

"""Playbook policy checks for contract fixtures."""
from __future__ import annotations

from typing import Any

DEFAULT_PLAYBOOKS: dict[str, list[dict[str, Any]]] = {
    "nda": [
        {"id": "nda-mutual", "pattern": "mutual", "label": "Mutual confidentiality required", "severity": "high"},
        {"id": "nda-law", "pattern": "required by law", "label": "Legal disclosure carve-out", "severity": "medium"},
    ],
    "msa": [
        {"id": "msa-dpa", "pattern": "data processing", "label": "DPA reference required", "severity": "high"},
        {"id": "msa-dpa2", "pattern": "dpa", "label": "DPA acronym present", "severity": "medium"},
    ],
    "dpa": [
        {"id": "dpa-scc", "pattern": "standard contractual clauses", "label": "SCC transfer mechanism", "severity": "high"},
        {"id": "dpa-transfer", "pattern": "transfer", "label": "Transfer clause present", "severity": "medium"},
    ],
}


def detect_playbook(doc_type: str) -> list[dict[str, Any]]:
    key = doc_type.lower()
    for name, rules in DEFAULT_PLAYBOOKS.items():
        if name in key:
            return rules
    return DEFAULT_PLAYBOOKS.get("nda", [])


def run_playbook_checks(text: str, doc_type: str = "nda") -> list[dict[str, Any]]:
    lower = text.lower()
    results: list[dict[str, Any]] = []
    for rule in detect_playbook(doc_type):
        hit = rule["pattern"].lower() in lower
        results.append(
            {
                "id": rule["id"],
                "label": rule["label"],
                "severity": rule["severity"],
                "passed": hit,
            }
        )
    return results

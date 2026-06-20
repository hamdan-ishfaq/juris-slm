"""Structured clause analysis from document text + RAG answer."""
from __future__ import annotations

import re
from typing import Any


def build_structured_analysis(answer: str, document_text: str, *, question: str) -> dict[str, Any]:
    lower_doc = document_text.lower()
    clauses: list[dict[str, Any]] = []

    patterns = [
        ("confidentiality", r"confidential"),
        ("disclosure", r"disclos"),
        ("termination", r"terminat"),
        ("data_processing", r"data processing|dpa"),
        ("transfer", r"transfer|scc|standard contractual"),
        ("liability", r"liabilit|indemnif"),
    ]
    for clause_type, pat in patterns:
        if re.search(pat, lower_doc, re.IGNORECASE):
            risk = "medium"
            if clause_type in ("liability", "transfer"):
                risk = "high"
            clauses.append(
                {
                    "clause_type": clause_type,
                    "risk_level": risk,
                    "recommendation": f"Review {clause_type.replace('_', ' ')} language against playbook.",
                }
            )

    return {
        "question": question,
        "summary": answer[:500],
        "clauses": clauses[:8],
    }

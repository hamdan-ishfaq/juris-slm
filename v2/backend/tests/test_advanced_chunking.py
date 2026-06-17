"""Unit tests for parent-child contract chunking (Phase 2.7)."""
from __future__ import annotations

from services.advanced_chunking import hierarchical_chunk

SAMPLE = """
Article 1 Definitions

The Disclosing Party means TechCorp Inc.
The Receiving Party means LegalAI Solutions GmbH.

Article 2 Confidentiality

The Receiving Party shall not disclose any Confidential Information to third parties
without prior written consent of the Disclosing Party.
"""


def test_hierarchical_chunk_creates_parent_metadata():
    chunks = hierarchical_chunk(SAMPLE)
    assert len(chunks) >= 2
    assert all("parent_content" in c for c in chunks)
    assert all("parent_id" in c for c in chunks)
    assert any("Confidentiality" in c.get("parent_title", "") for c in chunks)


def test_hierarchical_chunk_child_content_reasonable_size():
    chunks = hierarchical_chunk(SAMPLE, child_max=200)
    for c in chunks:
        assert len(c["content"]) <= 250

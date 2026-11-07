"""Phase 9E — WORM audit hash chain unit tests (no DB)."""
from __future__ import annotations

import pytest

from services.audit_chain import GENESIS_HASH, compute_row_hash


@pytest.mark.unit
def test_compute_row_hash_deterministic():
    payload = {"id": "abc", "action": "test"}
    h1 = compute_row_hash(GENESIS_HASH, payload)
    h2 = compute_row_hash(GENESIS_HASH, payload)
    assert h1 == h2
    assert len(h1) == 64

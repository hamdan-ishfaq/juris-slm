"""Runtime build fingerprint for deploy/restart verification."""
from __future__ import annotations

import hashlib
from functools import lru_cache
from pathlib import Path

_SRC = Path(__file__).resolve().parent.parent
_FINGERPRINT_FILES = (
    "main.py",
    "rate_limit.py",
    "services/rag.py",
    "services/security.py",
    "services/vector_store.py",
    "services/dev_master.py",
)


@lru_cache(maxsize=1)
def compute_build_hash() -> str:
    """Short hash of critical backend modules — changes when code is updated."""
    digest = hashlib.sha256()
    for rel in _FINGERPRINT_FILES:
        path = _SRC / rel
        if path.is_file():
            digest.update(rel.encode())
            digest.update(path.read_bytes())
    return digest.hexdigest()[:12]

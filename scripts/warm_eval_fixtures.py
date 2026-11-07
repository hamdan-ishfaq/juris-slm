#!/usr/bin/env python3
"""Upload eval contract fixtures and wait for Celery ingest before logical eval."""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from eval_common import api_reachable, ensure_fixture_documents, get_eval_user


def main() -> int:
    if not api_reachable():
        print("API not reachable — skip fixture warm-up")
        return 1
    user = get_eval_user()
    matter_id, doc_ids = ensure_fixture_documents(user["token"])
    print(f"Fixtures ready: matter={matter_id} docs={len(doc_ids)}")
    for name, doc_id in sorted(doc_ids.items()):
        print(f"  {name} -> {doc_id}")
    return 0


if __name__ == "__main__":
    sys.exit(main())

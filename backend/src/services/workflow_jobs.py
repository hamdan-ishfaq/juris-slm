"""Redis-backed workflow job status — Phase 9D."""
from __future__ import annotations

import json
import uuid
from typing import Any

from config import settings

_JOB_PREFIX = "workflow:job:"
_TTL_SECONDS = 86400


def _client():
    import redis

    return redis.from_url(settings.redis_url, decode_responses=True)


def create_job(job_type: str, *, meta: dict | None = None) -> str:
    job_id = str(uuid.uuid4())
    payload = {
        "job_id": job_id,
        "type": job_type,
        "status": "queued",
        "progress_step": "queued",
        "meta": meta or {},
        "report": None,
        "error": None,
    }
    _client().setex(f"{_JOB_PREFIX}{job_id}", _TTL_SECONDS, json.dumps(payload))
    return job_id


def update_job(job_id: str, **fields: Any) -> None:
    key = f"{_JOB_PREFIX}{job_id}"
    raw = _client().get(key)
    if not raw:
        return
    data = json.loads(raw)
    data.update(fields)
    _client().setex(key, _TTL_SECONDS, json.dumps(data))


def get_job(job_id: str) -> dict | None:
    raw = _client().get(f"{_JOB_PREFIX}{job_id}")
    if not raw:
        return None
    return json.loads(raw)

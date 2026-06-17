"""Celery worker health probe for /api/v1/status (Phase 0)."""
from __future__ import annotations

from celery import Celery

from config import settings


def get_celery_status(*, timeout: float = 2.0) -> dict:
    """Return worker reachability via Celery inspect ping."""
    try:
        app = Celery("juris_worker", broker=settings.redis_url, backend=settings.redis_url)
        inspect = app.control.inspect(timeout=timeout)
        ping = inspect.ping() or {}
        active = inspect.active() or {}
        active_tasks = sum(len(tasks) for tasks in active.values())
        return {
            "reachable": bool(ping),
            "workers": list(ping.keys()),
            "active_tasks": active_tasks,
        }
    except Exception as exc:
        return {
            "reachable": False,
            "workers": [],
            "active_tasks": 0,
            "error": str(exc),
        }

"""Admission control and priority for the one GPU (D-021, eval/load/PLAN.md step 4).

Ollama answers one request at a time and queues the rest first in, first out, so without this a gap analysis already
queued delays a user's question, and a tenth user waits behind nine others with no signal. Two lanes, shared through
Redis because chat runs in the API and gap analysis in the Celery worker:

- interactive (chat, document questions): admitted while fewer than ``gpu_queue_limit`` are running or waiting, and
  told how many are ahead; beyond that, rejected at once with a retry time (429 with Retry-After). The limit is an
  overload guard, not the queue: admitted requests wait in Ollama's first-in, first-out queue. Rejecting early and
  letting clients retry was measured and lost that order: at 12 users the p95 wait rose from 103 s to 169 s.
- background (gap analysis, graph extraction, ingest): before each model call, waits while any interactive request
  is in the system, so it never sits ahead of one in Ollama's queue. It waits at most ``gpu_background_max_wait_seconds``
  per call, so a steady stream of questions can't starve it.

Entries are timestamped members of a sorted set; ones older than ``gpu_slot_stale_seconds`` are dropped, so a crashed
request can't hold a slot. If Redis is down the gate lets everything through and logs it, as the answer cache does.
"""
from __future__ import annotations

import asyncio
import logging
import math
import time
import uuid
from contextlib import asynccontextmanager, contextmanager
from contextvars import ContextVar

from config import settings

logger = logging.getLogger(__name__)

KEY = "juris:gpu:interactive"
_LANE: ContextVar[str] = ContextVar("gpu_lane", default="interactive")

# Atomic across processes: drop stale entries, then admit only below the limit (ARGV[2] < 0 means admit regardless).
_ADMIT = """
redis.call('ZREMRANGEBYSCORE', KEYS[1], '-inf', ARGV[1])
local n = redis.call('ZCARD', KEYS[1])
local limit = tonumber(ARGV[2])
if limit >= 0 and n >= limit then return -n end
redis.call('ZADD', KEYS[1], ARGV[3], ARGV[4])
return n + 1
"""


class GpuBusy(Exception):
    def __init__(self, retry_after: int, in_system: int):
        super().__init__(f"GPU busy: {in_system} requests ahead, retry in {retry_after} s")
        self.retry_after = retry_after
        self.in_system = in_system


def _client():
    import redis

    return redis.from_url(settings.redis_url, decode_responses=True)


def retry_after_seconds(in_system: int) -> int:
    """Time until a slot is likely free: the requests ahead, served one per mean answer time per parallel slot."""
    parallel = max(settings.ollama_num_parallel, 1)
    wait = math.ceil((in_system - settings.gpu_queue_limit + 1) * settings.gpu_mean_answer_seconds / parallel)
    return min(max(wait, 1), 120)


def acquire(*, force: bool = False) -> str | None:
    """Take an interactive slot; raises GpuBusy when full. Returns a ticket for release(), or None if the gate is off."""
    return admit(force=force)[0]


def admit(*, force: bool = False) -> tuple[str | None, int]:
    """Like acquire(), also returning how many requests were already in the system (0 when the gate is off)."""
    if not settings.gpu_gate_enabled:
        return None, 0
    ticket = uuid.uuid4().hex
    now = time.time()
    try:
        n = int(_client().eval(_ADMIT, 1, KEY, now - settings.gpu_slot_stale_seconds,
                               -1 if force else settings.gpu_queue_limit, now, ticket))
    except Exception:
        logger.warning("GPU gate unavailable; admitting without a limit", exc_info=True)
        return None, 0
    if n < 0:
        raise GpuBusy(retry_after_seconds(-n), -n)
    return ticket, n - 1


def wait_estimate_seconds(ahead: int) -> int:
    return math.ceil(ahead * settings.gpu_mean_answer_seconds / max(settings.ollama_num_parallel, 1))


def release(ticket: str | None) -> None:
    if not ticket:
        return
    try:
        _client().zrem(KEY, ticket)
    except Exception:
        logger.warning("GPU gate release failed; the slot expires on its own", exc_info=True)


@asynccontextmanager
async def interactive_slot(*, force: bool = False):
    ticket = acquire(force=force)
    try:
        yield
    finally:
        release(ticket)


def interactive_in_system() -> int:
    try:
        client = _client()
        client.zremrangebyscore(KEY, "-inf", time.time() - settings.gpu_slot_stale_seconds)
        return int(client.zcard(KEY))
    except Exception:
        return 0


@contextmanager
def background_lane():
    """Mark model calls made inside this block as background work."""
    token = _LANE.set("background")
    try:
        yield
    finally:
        _LANE.reset(token)


async def yield_to_interactive() -> float:
    """In the background lane, wait until no interactive request is in the system. Returns the seconds waited."""
    if _LANE.get() != "background" or not settings.gpu_gate_enabled:
        return 0.0
    started = time.monotonic()
    while interactive_in_system() and time.monotonic() - started < settings.gpu_background_max_wait_seconds:
        await asyncio.sleep(settings.gpu_background_poll_seconds)
    return time.monotonic() - started

"""GPU admission and priority (D-021): full queue rejected with a retry time, background work yields to users."""
import asyncio

import pytest

from services import gpu_gate


class FakeRedis:
    """The sorted-set calls the gate makes, with the admit script run in Python."""

    def __init__(self):
        self.z: dict[str, float] = {}

    def _prune(self, max_score):
        self.z = {m: s for m, s in self.z.items() if s > float(max_score)}

    def eval(self, _script, _nkeys, _key, stale_before, limit, now, ticket):
        self._prune(stale_before)
        n = len(self.z)
        if limit >= 0 and n >= limit:
            return -n
        self.z[ticket] = float(now)
        return n + 1

    def zrem(self, _key, ticket):
        self.z.pop(ticket, None)

    def zremrangebyscore(self, _key, _lo, hi):
        self._prune(hi)

    def zcard(self, _key):
        return len(self.z)


@pytest.fixture
def fake(monkeypatch):
    redis = FakeRedis()
    monkeypatch.setattr(gpu_gate, "_client", lambda: redis)
    monkeypatch.setattr(gpu_gate.settings, "gpu_gate_enabled", True)
    monkeypatch.setattr(gpu_gate.settings, "gpu_queue_limit", 2)
    monkeypatch.setattr(gpu_gate.settings, "gpu_mean_answer_seconds", 8.5)
    monkeypatch.setattr(gpu_gate.settings, "ollama_num_parallel", 1)
    monkeypatch.setattr(gpu_gate.settings, "gpu_background_poll_seconds", 0.01)
    return redis


def test_requests_beyond_the_limit_are_rejected_with_a_retry_time(fake):
    first, second = gpu_gate.acquire(), gpu_gate.acquire()
    with pytest.raises(gpu_gate.GpuBusy) as busy:
        gpu_gate.acquire()
    assert busy.value.in_system == 2
    assert busy.value.retry_after == 9  # one answer must finish first: ceil(8.5)
    gpu_gate.release(first)
    assert gpu_gate.acquire()  # a freed slot admits again
    gpu_gate.release(second)


def test_a_queued_job_is_counted_even_when_full(fake):
    gpu_gate.acquire()
    gpu_gate.acquire()
    assert gpu_gate.acquire(force=True)
    assert fake.zcard("k") == 3


def test_a_crashed_request_does_not_hold_its_slot(fake, monkeypatch):
    monkeypatch.setattr(gpu_gate.settings, "gpu_slot_stale_seconds", 600)
    fake.z = {"crashed-1": 0.0, "crashed-2": 0.0}  # stamped long ago
    assert gpu_gate.acquire()


def test_the_gate_fails_open_when_redis_is_down(monkeypatch):
    def broken():
        raise ConnectionError("redis down")

    monkeypatch.setattr(gpu_gate, "_client", broken)
    monkeypatch.setattr(gpu_gate.settings, "gpu_gate_enabled", True)
    assert gpu_gate.acquire() is None
    gpu_gate.release(None)


def test_background_calls_wait_for_interactive_requests(fake, monkeypatch):
    monkeypatch.setattr(gpu_gate.settings, "gpu_background_max_wait_seconds", 5)
    ticket = gpu_gate.acquire()

    async def scenario():
        async def user_finishes():
            await asyncio.sleep(0.1)
            gpu_gate.release(ticket)

        with gpu_gate.background_lane():
            waited, _ = await asyncio.gather(gpu_gate.yield_to_interactive(), user_finishes())
        return waited

    assert asyncio.run(scenario()) >= 0.1


def test_interactive_calls_never_wait(fake):
    gpu_gate.acquire()
    assert asyncio.run(gpu_gate.yield_to_interactive()) == 0.0


def test_background_waits_are_capped(fake, monkeypatch):
    monkeypatch.setattr(gpu_gate.settings, "gpu_background_max_wait_seconds", 0.05)
    gpu_gate.acquire()

    async def scenario():
        with gpu_gate.background_lane():
            return await gpu_gate.yield_to_interactive()

    assert 0.05 <= asyncio.run(scenario()) < 1

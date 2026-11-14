"""The answer cache must not serve an answer from before the law corpus changed."""
from services import query_cache


class FakeRedis:
    def __init__(self):
        self.data = {}

    def get(self, key):
        return self.data.get(key)

    def setex(self, key, _ttl, value):
        self.data[key] = value

    def incr(self, key):
        self.data[key] = str(int(self.data.get(key) or 0) + 1)
        return int(self.data[key])


def _use(monkeypatch, fake):
    monkeypatch.setattr(query_cache.settings, "query_cache_enabled", True)
    monkeypatch.setattr(query_cache, "_client", lambda: fake)


def test_a_cached_answer_is_served_until_the_corpus_changes(monkeypatch):
    fake = FakeRedis()
    _use(monkeypatch, fake)
    query_cache.set_cached_answer("What is Article 6?", use_law_corpus=True, document_id=None, payload={"answer": "old"})
    assert query_cache.get_cached_answer("what is  article 6?", use_law_corpus=True, document_id=None) == {"answer": "old"}

    query_cache.bump_corpus_version()
    assert query_cache.get_cached_answer("What is Article 6?", use_law_corpus=True, document_id=None) is None


def test_bumping_the_version_survives_redis_being_down(monkeypatch):
    def broken():
        raise ConnectionError("redis down")

    monkeypatch.setattr(query_cache, "_client", broken)
    query_cache.bump_corpus_version()  # logs, doesn't raise

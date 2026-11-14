"""The answer cache must not serve an answer from before the law corpus changed."""
import numpy as np

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

    def lpush(self, key, value):
        self.data.setdefault(key, []).insert(0, value)

    def ltrim(self, key, start, end):
        self.data[key] = self.data.get(key, [])[start : end + 1]

    def lrange(self, key, start, end):
        items = self.data.get(key, [])
        return items[start:] if end == -1 else items[start : end + 1]

    def expire(self, _key, _ttl):
        pass


def _use(monkeypatch, fake):
    monkeypatch.setattr(query_cache.settings, "query_cache_enabled", True)
    monkeypatch.setattr(query_cache.settings, "semantic_cache_enabled", True)
    monkeypatch.setattr(query_cache.settings, "semantic_cache_threshold", 0.95)
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


def _unit(*xs):
    v = np.array(xs, dtype=np.float32)
    return v / np.linalg.norm(v)


def test_a_rewording_with_the_same_provision_gets_the_cached_answer(monkeypatch):
    fake = FakeRedis()
    _use(monkeypatch, fake)
    query_cache.set_cached_answer("When can legitimate interests be a lawful basis under Article 6(1)(f)?",
                                  use_law_corpus=True, document_id=None, payload={"answer": "6(1)(f)"},
                                  org_id="org-a", vector_fn=lambda: _unit(1, 0.1, 0))
    hit = query_cache.get_cached_answer("Under Article 6(1)(f), when may a controller rely on legitimate interests?",
                                        use_law_corpus=True, document_id=None, org_id="org-a", vector_fn=lambda: _unit(1, 0.12, 0))
    assert hit["answer"] == "6(1)(f)"
    assert hit["cache_match"]["similarity"] >= 0.95


def test_a_different_point_of_the_same_article_is_never_served(monkeypatch):
    fake = FakeRedis()
    _use(monkeypatch, fake)
    query_cache.set_cached_answer("When can legitimate interests be a lawful basis under Article 6(1)(f)?",
                                  use_law_corpus=True, document_id=None, payload={"answer": "6(1)(f)"},
                                  org_id="org-a", vector_fn=lambda: _unit(1, 0, 0))
    # Near-identical embedding, different point: the guard refuses it.
    assert query_cache.get_cached_answer("When can legitimate interests be a lawful basis under Article 6(1)(e)?",
                                         use_law_corpus=True, document_id=None, org_id="org-a",
                                         vector_fn=lambda: _unit(1, 0, 0)) is None


def test_one_organisation_never_gets_another_organisations_answer(monkeypatch):
    fake = FakeRedis()
    _use(monkeypatch, fake)
    query_cache.set_cached_answer("What is Article 6?", use_law_corpus=True, document_id=None,
                                  payload={"answer": "a"}, org_id="org-a", vector_fn=lambda: _unit(1, 0, 0))
    for vector_fn in (None, lambda: _unit(1, 0, 0)):
        assert query_cache.get_cached_answer("What is Article 6?", use_law_corpus=True, document_id=None,
                                             org_id="org-b", vector_fn=vector_fn) is None


def test_a_corpus_change_also_empties_the_semantic_index(monkeypatch):
    fake = FakeRedis()
    _use(monkeypatch, fake)
    query_cache.set_cached_answer("What is Article 6?", use_law_corpus=True, document_id=None,
                                  payload={"answer": "a"}, vector_fn=lambda: _unit(1, 0, 0))
    query_cache.bump_corpus_version()
    assert query_cache.get_cached_answer("Explain Article 6.", use_law_corpus=True, document_id=None,
                                         vector_fn=lambda: _unit(1, 0, 0)) is None


def test_the_product_guard_matches_the_one_that_was_scored():
    import importlib.util
    import json
    from pathlib import Path

    root = Path(__file__).resolve().parents[2]
    spec = importlib.util.spec_from_file_location("sce", root / "eval" / "load" / "semantic_cache_eval.py")
    scored = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(scored)
    for name in ("cache_pairs.jsonl", "cache_pairs_v2.jsonl"):
        for line in (root / "eval" / "load" / name).read_text().splitlines():
            probe = json.loads(line)["probe"]
            provisions, laws = scored.signature(probe)
            assert query_cache.cache_signature(probe) == [list(provisions), list(laws)], probe

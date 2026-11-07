"""A question that names a document should search that document first, and only when the name is clear."""
import asyncio
import uuid

from services import rag
from services.document_routing import focus_question, route_to_document
from services.rrf import rrf_merge

TITLES = {
    "keep": "privacy_qa/Keep.txt",
    "groupon": "privacy_qa/Groupon.txt",
    "marketing": "cuad/Loop Industries, Inc. - Marketing Agreement.txt",
    "seeed": "contractnli/NDA-Seeed.txt",
    "bridgebio": "maud/BridgeBio_Eidos_Therapeutics.txt",
    "squashed": "cuad/AFSALABANCORPINC_08_01_1996-EX-1.1-AGENCY AGREEMENT.txt",
}


def test_named_document_is_found():
    assert route_to_document("In Groupon's privacy policy, do they sell my data?", TITLES) == "groupon"


def test_a_whole_title_beats_a_substring_of_another():
    assert route_to_document('Consider "Keep"\'s privacy policy; who can see my data?', TITLES) == "keep"


def test_a_name_squashed_in_a_filename_is_found():
    question = "Consider the Agency Agreement between AFSALA Bancorp, Inc. and others; What is the term?"
    assert route_to_document(question, TITLES) == "squashed"


def test_question_naming_nothing_is_not_routed():
    assert route_to_document("What is the governing law for termination disputes?", TITLES) is None


def test_ambiguous_question_is_not_routed():
    titles = {"a": "Acme Supply Agreement.txt", "b": "Acme Service Agreement.txt"}
    assert route_to_document("What does the Acme contract say about notice?", titles) is None


def test_no_documents_means_no_route():
    assert route_to_document("In Groupon's policy, do they sell data?", {}) is None


def test_focus_keeps_what_follows_the_naming_clause():
    title = TITLES["groupon"]
    assert focus_question("In Groupon's privacy policy, do they sell my data?", title) == "do they sell my data?"
    assert focus_question('Consider "Groupon"\'s privacy policy; will they share my data?', title) == "will they share my data?"


def test_focus_handles_a_name_with_commas():
    question = "Consider the Agency Agreement between AFSALA Bancorp, Inc., Amsterdam Bank; What is the term of it?"
    assert focus_question(question, TITLES["squashed"]).endswith("What is the term of it?")


def test_focus_removes_the_name_when_no_clause_follows():
    assert focus_question("What does Groupon say about location data?", TITLES["groupon"]) == "What does say about location data?"


def test_weighted_merge_favours_the_heavier_list():
    a = [{"id": 1}, {"id": 2}]
    b = [{"id": 3}, {"id": 4}]
    assert [hit["id"] for hit in rrf_merge([a, b], top_k=4, weights=[4, 1])][:2] == [1, 2]


def test_retrieval_searches_the_named_document_and_keeps_global_results(monkeypatch):
    doc = uuid.uuid4()
    other = uuid.uuid4()
    calls = []

    async def fake_titles(_db, _ids):
        return {doc: "Groupon.txt", other: "Keep.txt"}

    async def fake_embed(question, *, use_hyde):
        return question, None

    async def fake_retrieve(_db, question, _vector, *, accessible_ids, **_kwargs):
        calls.append((question, accessible_ids))
        if accessible_ids == {doc}:
            return [{"id": 1, "content": "scoped 1", "metadata": {}}]
        return [{"id": 2, "content": "global 2", "metadata": {}}]

    monkeypatch.setattr(rag, "_document_titles", fake_titles)
    monkeypatch.setattr(rag, "_embed_query", fake_embed)
    monkeypatch.setattr(rag, "_retrieve", fake_retrieve)
    monkeypatch.setattr(rag, "score_hits", lambda _q, hits: [{**h, "rerank_score": 1.0} for h in hits])
    monkeypatch.setattr(rag.settings, "rag_rerank_k", 5)
    monkeypatch.setattr(rag.settings, "crag_retry_enabled", False)
    question = "In Groupon's privacy policy, do they sell my data?"
    ranked = asyncio.run(
        rag._retrieve_and_rank(
            None,
            question,
            accessible_ids={doc, other},
            include_law=False,
            user_role="member",
            doc_uuid=None,
            use_hyde=False,
        )
    )
    assert [hit["id"] for hit in ranked] == [1, 2]
    assert ("do they sell my data?", {doc}) in calls
    assert (question, {doc, other}) in calls

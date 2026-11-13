"""A question that names a document should search that document first, and only when the name is clear."""
import asyncio
import uuid

from services import rag
from services.document_routing import document_description, focus_question, naming_clause, route_to_document
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
    assert route_to_document("What does Groupon say about my data?", TITLES) == "groupon"


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


def test_words_common_to_many_titles_do_not_identify_a_document():
    titles = {i: f"Company{i} Non-Disclosure Agreement.txt" for i in range(30)}
    titles["target"] = "Grindrod Non-Disclosure Agreement.txt"
    question = "Consider Grindrod's Non-Disclosure Agreement; may the party retain copies?"
    assert route_to_document(question, titles) == "target"
    assert route_to_document("What does a Non-Disclosure Agreement usually require?", titles) is None


def test_words_in_the_question_body_do_not_route():
    titles = {"nu": "NU Confidentiality Agreement.txt", "other": "Zephyr Supply Contract.txt", "third": "Keep.txt"}
    question = "Consider this party's agreement; Does the document protect confidentiality information?"
    assert route_to_document(question, titles) != "nu"


def test_a_word_in_many_titles_stays_weak_in_a_large_collection():
    titles = {i: f"Company{i} Confidentiality Non-Disclosure.txt" for i in range(40)}
    titles["target"] = "SupplementOne-NDA.txt"
    question = "Consider SupplementOne's Non-Disclosure Agreement; may the party retain copies?"
    assert route_to_document(question, titles) == "target"


def test_ordinary_words_matching_a_title_do_not_route():
    titles = {"a": "Audit Services Contract.txt", "b": "Merger Terms.txt", "c": "Keep.txt"}
    assert route_to_document("What are the audit rights?", titles) is None
    assert route_to_document("What does the merger say about closing?", titles) is None


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


def test_naming_clause_needs_a_later_part_to_ask_about():
    assert naming_clause("Consider the Acme Supply Agreement; is there a cap on liability?") == (
        "Consider the Acme Supply Agreement"
    )
    assert naming_clause("Which of our contracts cap liability?") is None
    assert naming_clause("Is there an anti-assignment clause in this contract?") is None


def test_description_holds_the_filename_and_the_first_and_last_paragraphs():
    text = "SUPPLY AGREEMENT between Acme Inc. and Beta LLC\n\n" + "Middle. " * 200 + "\n\nSigned by Acme and Beta."
    description = document_description("cuad/Acme_Beta-Supply.txt", text)
    assert description.splitlines()[0] == "acme_beta-supply"
    assert "SUPPLY AGREEMENT between Acme Inc." in description
    assert description.endswith("Signed by Acme and Beta.")
    assert "Middle." not in description


def _fallback_setup(monkeypatch, nearest):
    docs = [uuid.uuid4() for _ in range(4)]
    searched = []

    async def fake_titles(_db, _ids):
        return {doc: f"Unrelated{n}.txt" for n, doc in enumerate(docs)}

    async def fake_embed(question, *, use_hyde):
        return question, None

    async def fake_nearest(_db, clause_vec, ids, *, limit):
        searched.append(("nearest", clause_vec, limit))
        return [docs[i] for i in nearest]

    async def fake_retrieve(_db, question, _vector, *, accessible_ids, **_kwargs):
        (doc,) = accessible_ids
        searched.append(("document", doc))
        return [{"id": f"{doc}-{rank}", "content": f"{doc} {rank}"} for rank in range(20)]

    monkeypatch.setattr(rag, "_document_titles", fake_titles)
    monkeypatch.setattr(rag, "_embed_query", fake_embed)
    monkeypatch.setattr(rag, "nearest_documents", fake_nearest)
    monkeypatch.setattr(rag, "_retrieve", fake_retrieve)
    return docs, searched


def test_without_a_filename_match_the_nearest_documents_are_searched_with_equal_weight(monkeypatch):
    docs, searched = _fallback_setup(monkeypatch, nearest=[2, 0, 1])
    global_hits = [{"id": f"global-{rank}", "content": f"global {rank}"} for rank in range(20)]
    question = "Consider the Supply Agreement between Acme and Beta; is there a cap on liability?"
    merged = asyncio.run(
        rag._merge_named_document(None, question, global_hits, accessible_ids=set(docs), user_role="member", org_id=None)
    )
    assert searched[0] == ("nearest", "Consider the Supply Agreement between Acme and Beta", 3)
    assert [entry[1] for entry in searched[1:]] == [docs[2], docs[0], docs[1]]
    # Equal weights: the global search still holds places in the top 20.
    assert sum(hit["id"].startswith("global") for hit in merged) == 5


def test_a_question_across_all_documents_is_not_pulled_towards_a_few(monkeypatch):
    docs, searched = _fallback_setup(monkeypatch, nearest=[0, 1, 2])
    global_hits = [{"id": "global-0", "content": "global 0"}]
    merged = asyncio.run(
        rag._merge_named_document(
            None, "Which contracts cap liability?", global_hits, accessible_ids=set(docs), user_role="member", org_id=None
        )
    )
    assert merged == global_hits
    assert searched == []

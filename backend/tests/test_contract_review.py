"""The checklist review: one bounded step per item, quotes checked, failures reported per item (D-017)."""
import asyncio
import json
import uuid

from services.agents import contract_review as cr

ITEM = cr.COMMERCIAL_CHECKLIST[0]  # Governing Law
CHUNKS = [{"id": 11, "content": "12. Governing Law. This Agreement shall be governed by the laws of the State of New York."}]


def _asker(*replies):
    calls = []

    async def ask(messages):
        calls.append(messages)
        reply = replies[len(calls) - 1]
        if isinstance(reply, Exception):
            raise reply
        return reply if isinstance(reply, str) else json.dumps(reply)

    return ask, calls


def _check(ask, chunks=CHUNKS, calls_left=2):
    return asyncio.run(cr.check_item(ITEM, chunks, ask=ask, calls_left=calls_left))


def test_a_present_clause_is_cited_by_the_chunk_holding_the_quote():
    ask, calls = _asker({"present": True, "quote": "governed by the laws of the State of New York", "explanation": "x"})
    result = _check(ask)
    assert (result.status, result.chunk_id, result.calls, len(calls)) == ("present", "11", 1, 1)


def test_a_missing_clause_needs_no_quote():
    ask, _ = _asker({"present": False, "quote": "", "explanation": "none"})
    assert _check(ask).status == "missing"


def test_a_quote_not_in_the_text_is_asked_for_once_more():
    ask, calls = _asker(
        {"present": True, "quote": "governed by the laws of California", "explanation": "x"},
        {"present": True, "quote": "the laws of the State of New York", "explanation": "x"},
    )
    result = _check(ask)
    assert result.status == "present" and result.calls == 2
    assert "wasn't found" in calls[1][-1]["content"]


def test_a_quote_never_found_is_not_verified():
    wrong = {"present": True, "quote": "governed by the laws of California", "explanation": "x"}
    ask, _ = _asker(wrong, wrong)
    assert _check(ask).status == "not_verified"


def test_the_model_failing_marks_the_item_not_checked():
    ask, _ = _asker(RuntimeError("Ollama request failed: connection refused"))
    result = _check(ask)
    assert result.status == "not_checked" and "connection refused" in result.error


def test_a_reply_that_isnt_the_schema_marks_the_item_not_checked():
    ask, _ = _asker("Sure! The governing law is New York.")
    assert _check(ask).status == "not_checked"


def test_no_call_is_made_without_budget():
    ask, calls = _asker()
    result = _check(ask, calls_left=0)
    assert result.status == "not_checked" and calls == []


def test_the_review_stops_calling_the_model_when_the_budget_is_spent(monkeypatch):
    async def fake_retrieve(*_args, **_kwargs):
        return CHUNKS

    monkeypatch.setattr("services.rag._retrieve_and_rank", fake_retrieve)
    ask, calls = _asker(*([{"present": False, "quote": "", "explanation": ""}] * 10))
    steps = []

    async def step(name, detail):
        steps.append((name, detail))

    review = asyncio.run(
        cr.review_contract(None, uuid.uuid4(), checklist=cr.COMMERCIAL_CHECKLIST[:5], ask=ask, step=step, budget=3)
    )
    assert review.calls == 3 and len(calls) == 3
    assert [item.status for item in review.items] == ["missing"] * 3 + ["not_checked"] * 2
    assert ("budget_reached", {"item": cr.COMMERCIAL_CHECKLIST[3].key}) in steps


def test_an_empty_document_is_reported_missing_without_a_call(monkeypatch):
    async def nothing(*_args, **_kwargs):
        return []

    monkeypatch.setattr("services.rag._retrieve_and_rank", nothing)
    ask, calls = _asker()
    review = asyncio.run(cr.review_contract(None, uuid.uuid4(), checklist=cr.COMMERCIAL_CHECKLIST[:2], ask=ask))
    assert [item.status for item in review.items] == ["missing", "missing"] and calls == []

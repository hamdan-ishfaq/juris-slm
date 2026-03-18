import asyncio

import pytest
from sqlalchemy import select

from src.db import ChatMessage


@pytest.mark.asyncio
async def test_chat_query_persists_messages_without_prompt_recursion(client, app, auth_headers, db_session):
    headers, _ = await auth_headers()
    app.state.mock_query_manager.next_answer = "Hello there"

    first = await client.post("/chat/query", json={"query": "Hi"}, headers=headers)
    second = await client.post("/chat/query", json={"query": "Hi"}, headers=headers)

    assert first.status_code == 200
    assert second.status_code == 200

    await asyncio.sleep(0.05)
    result = await db_session.execute(select(ChatMessage).order_by(ChatMessage.timestamp.asc()))
    rows = result.scalars().all()
    assert len(rows) == 4

    user_contents = [m.content for m in rows if m.role == "user"]
    assert user_contents == ["Hi", "Hi"]

    forbidden_markers = ["History:", "<retrieved_data>", "<|system|>", "USER QUESTION"]
    for row in rows:
        assert not any(marker in row.content for marker in forbidden_markers)


@pytest.mark.asyncio
async def test_chat_query_returns_mocked_response_and_trace_sources(client, app, auth_headers):
    headers, _ = await auth_headers()
    app.state.mock_query_manager.next_answer = "Mocked response from query manager"

    response = await client.post("/chat/query", json={"query": "Summarize clause 12"}, headers=headers)

    assert response.status_code == 200
    body = response.json()
    assert body["answer"] == "Mocked response from query manager"
    assert body["status"] == "success"
    assert len(body["sources"]) > 0


@pytest.mark.asyncio
async def test_chat_history_endpoint_returns_persisted_messages(client, auth_headers):
    headers, _ = await auth_headers()

    await client.post("/chat/query", json={"query": "Question A"}, headers=headers)
    await client.post("/chat/query", json={"query": "Question B"}, headers=headers)
    await asyncio.sleep(0.05)

    history = await client.get("/chat/history?limit=50", headers=headers)
    assert history.status_code == 200

    body = history.json()
    assert body["message_count"] == 4
    assert [m["role"] for m in body["messages"]] == ["user", "assistant", "user", "assistant"]
    assert body["messages"][0]["content"] == "Question A"


@pytest.mark.asyncio
async def test_context_window_is_limited_to_last_six_messages(client, app, auth_headers):
    headers, _ = await auth_headers()

    for idx in range(8):
        response = await client.post("/chat/query", json={"query": f"q{idx}"}, headers=headers)
        assert response.status_code == 200

    last_call = app.state.mock_query_manager.calls[-1]
    assert last_call["history_window_count"] == 6


@pytest.mark.asyncio
async def test_chat_query_requires_authentication(client):
    response = await client.post("/chat/query", json={"query": "hello"})
    assert response.status_code == 401
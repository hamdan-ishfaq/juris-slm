import pytest


@pytest.mark.asyncio
async def test_chat_query_rejects_empty_payload(client, auth_headers):
    headers, _ = await auth_headers()
    response = await client.post("/chat/query", json={"query": "   "}, headers=headers)

    assert response.status_code == 400
    assert "cannot be blank" in response.json()["detail"].lower()


@pytest.mark.asyncio
async def test_auth_me_requires_header(client):
    response = await client.get("/auth/me")
    assert response.status_code == 401
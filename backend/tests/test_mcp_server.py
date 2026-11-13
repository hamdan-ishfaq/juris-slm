"""The MCP server refuses requests without the token, and offers only read-only tools (D-018)."""
import hashlib

import pytest
from starlette.testclient import TestClient

import mcp_server

TOKEN = "test-token-for-the-mcp-server"
HEADERS = {"Accept": "application/json, text/event-stream", "Content-Type": "application/json"}
INIT = {"jsonrpc": "2.0", "id": 1, "method": "initialize", "params": {
    "protocolVersion": "2025-06-18", "capabilities": {}, "clientInfo": {"name": "test", "version": "1"}}}
LIST = {"jsonrpc": "2.0", "id": 2, "method": "tools/list", "params": {}}


@pytest.fixture
def client(monkeypatch):
    monkeypatch.setattr(mcp_server.settings, "mcp_token_sha256", hashlib.sha256(TOKEN.encode()).hexdigest())
    with TestClient(mcp_server.build_app(), base_url="http://localhost:8003") as c:
        yield c


def test_no_token_is_refused(client):
    r = client.post("/mcp", json=INIT, headers=HEADERS)
    assert r.status_code == 401 and r.headers["www-authenticate"] == "Bearer"


def test_a_wrong_token_is_refused(client):
    r = client.post("/mcp", json=INIT, headers={**HEADERS, "Authorization": "Bearer not-the-token"})
    assert r.status_code == 401


def test_without_a_configured_token_everything_is_refused(monkeypatch):
    monkeypatch.setattr(mcp_server.settings, "mcp_token_sha256", "")
    with TestClient(mcp_server.build_app(), base_url="http://localhost:8003") as c:
        r = c.post("/mcp", json=INIT, headers={**HEADERS, "Authorization": f"Bearer {TOKEN}"})
    assert r.status_code == 401


def test_only_the_three_read_only_tools_are_offered(client):
    auth = {**HEADERS, "Authorization": f"Bearer {TOKEN}"}
    assert client.post("/mcp", json=INIT, headers=auth).status_code == 200
    r = client.post("/mcp", json=LIST, headers={**auth, "MCP-Protocol-Version": "2025-06-18"})
    assert r.status_code == 200, r.text
    names = {tool["name"] for tool in r.json()["result"]["tools"]}
    assert names == {"search_law", "get_article", "check_citation"}

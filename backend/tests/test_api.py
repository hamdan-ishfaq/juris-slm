# test_api.py
# tests/test_api.py - Integration tests for API
import pytest
from fastapi.testclient import TestClient
from src.api import create_app

client = TestClient(create_app())

def test_health():
    response = client.get("/health")
    assert response.status_code == 200
    assert "status" in response.json()

def test_query_empty():
    response = client.post("/query", json={"query": "test", "role": "admin"})
    assert response.status_code == 200
    # Assuming no data initially

def test_upload():
    # Mock upload test
    pass
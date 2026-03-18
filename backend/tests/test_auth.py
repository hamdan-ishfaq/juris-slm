from datetime import datetime, timezone

import pytest
from jose import jwt

import src.auth as auth_module
from src.auth import get_password_hash, verify_password


@pytest.mark.asyncio
async def test_register_success(client):
    payload = {"email": "new_user@example.com", "password": "SecurePass123!"}
    response = await client.post("/auth/register", json=payload)

    assert response.status_code == 201
    body = response.json()
    assert body["email"] == payload["email"]
    assert "id" in body


@pytest.mark.asyncio
async def test_register_duplicate_email(client):
    payload = {"email": "duplicate@example.com", "password": "SecurePass123!"}
    first = await client.post("/auth/register", json=payload)
    second = await client.post("/auth/register", json=payload)

    assert first.status_code == 201
    assert second.status_code == 400
    assert "already" in second.json()["detail"].lower()


@pytest.mark.asyncio
async def test_login_success_and_jwt_claims(client):
    register_payload = {"email": "jwt_user@example.com", "password": "SecurePass123!"}
    await client.post("/auth/register", json=register_payload)

    response = await client.post("/auth/login", json=register_payload)
    assert response.status_code == 200

    body = response.json()
    assert body["token_type"] == "bearer"
    token = body["access_token"]

    decoded = jwt.decode(token, auth_module.SECRET_KEY, algorithms=[auth_module.ALGORITHM])
    assert decoded.get("sub")
    assert decoded.get("role") == "user"
    assert decoded.get("exp")
    assert datetime.fromtimestamp(decoded["exp"], tz=timezone.utc) > datetime.now(timezone.utc)


@pytest.mark.asyncio
async def test_login_invalid_credentials(client):
    await client.post(
        "/auth/register",
        json={"email": "invalid_login@example.com", "password": "SecurePass123!"},
    )

    response = await client.post(
        "/auth/login",
        json={"email": "invalid_login@example.com", "password": "WrongPass123!"},
    )

    assert response.status_code == 401
    assert "invalid" in response.json()["detail"].lower()


def test_password_hashing_uses_unique_salts():
    password = "SamePassword123!"
    hash_a = get_password_hash(password)
    hash_b = get_password_hash(password)

    assert hash_a != hash_b
    assert verify_password(password, hash_a)
    assert verify_password(password, hash_b)
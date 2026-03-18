import pytest

from src.db import UserRole


@pytest.mark.asyncio
async def test_upload_pdf_success_and_ingestion_called(client, app, auth_headers):
    headers, _ = await auth_headers()
    files = {"file": ("contract.pdf", b"%PDF-1.4\n%mock-pdf", "application/pdf")}

    response = await client.post("/documents/upload", headers=headers, files=files)

    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "success"
    assert body["doc_id"] == "test-doc-id"

    assert len(app.state.mock_ingestion_manager.calls) == 1
    call = app.state.mock_ingestion_manager.calls[0]
    assert call["access_level"] == "level_1"


@pytest.mark.asyncio
async def test_upload_rejects_non_pdf_mime(client, auth_headers):
    headers, _ = await auth_headers()
    files = {"file": ("notes.txt", b"hello", "text/plain")}

    response = await client.post("/documents/upload", headers=headers, files=files)

    assert response.status_code == 400
    assert "only .pdf" in response.json()["detail"].lower()


@pytest.mark.asyncio
async def test_upload_rejects_large_file(client, auth_headers):
    headers, _ = await auth_headers()
    huge_payload = b"x" * (50 * 1024 * 1024 + 1)
    files = {"file": ("large.pdf", huge_payload, "application/pdf")}

    response = await client.post("/documents/upload", headers=headers, files=files)

    assert response.status_code == 413
    assert "file too large" in response.json()["detail"].lower()


@pytest.mark.asyncio
async def test_normal_user_forbidden_on_owner_delete_route(client, auth_headers):
    owner_headers, owner_user = await auth_headers(role=UserRole.OWNER)
    user_headers, _ = await auth_headers(role=UserRole.USER)

    response = await client.delete(f"/admin/users/{owner_user.id}", headers=user_headers)

    assert owner_headers["Authorization"].startswith("Bearer ")
    assert response.status_code == 403
    assert "owner role required" in response.json()["detail"].lower()
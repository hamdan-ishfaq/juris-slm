"""Phase 9E — audit verify API integration tests."""
from __future__ import annotations

import asyncio
import uuid

import pytest
from sqlalchemy import select, text

from api_helpers import api_request, register_user
from db import AuditEvent, Organization, User, async_session_factory
from services.audit_chain import GENESIS_HASH, hash_for_event, verify_chain
from services.audit_log import log_audit


@pytest.mark.integration
def test_audit_verify_passes(api_up):
    owner = register_user(org_name=f"Worm-{uuid.uuid4().hex[:6]}")
    r = api_request(
        "POST",
        "/api/v1/matters",
        token=owner["token"],
        json_body={"name": "Worm Matter", "description": "audit chain"},
    )
    assert r.status_code == 200

    r = api_request("GET", "/api/v1/audit/verify", token=owner["token"])
    assert r.status_code == 200
    body = r.json()
    assert body["valid"] is True
    assert body["events_checked"] >= 1

    r = api_request("POST", "/api/v1/audit/seal", token=owner["token"])
    assert r.status_code == 200
    seal = r.json()
    assert seal["sealed"] is True
    assert seal["chain_tail_hash"]
    assert seal["event_count"] >= 1


@pytest.mark.integration
def test_member_cannot_verify_audit(api_up):
    member = register_user()
    r = api_request("GET", "/api/v1/audit/verify", token=member["token"])
    assert r.status_code == 403


@pytest.mark.integration
def test_log_audit_builds_chain(api_up):
    async def _run() -> None:
        org_id = uuid.uuid4()
        user_id = uuid.uuid4()
        async with async_session_factory() as db:
            org = Organization(id=org_id, name="Chain Org", slug=f"chain-{uuid.uuid4().hex[:8]}")
            db.add(org)
            user = User(
                id=user_id,
                email=f"chain-{uuid.uuid4().hex[:8]}@test.local",
                password_hash="x",
                org_id=org_id,
                role="owner",
            )
            db.add(user)
            await db.flush()
            await log_audit(db, user, "test_action", "matter", resource_id="m1", details={"k": "v"})
            await log_audit(db, user, "test_action_2", "matter", resource_id="m2")
            await db.commit()

            rows = (
                await db.execute(
                    select(AuditEvent)
                    .where(AuditEvent.org_id == org_id)
                    .order_by(AuditEvent.timestamp.asc(), AuditEvent.id.asc())
                )
            ).scalars().all()
            assert len(rows) == 2
            assert rows[0].prev_hash == GENESIS_HASH
            assert rows[0].row_hash == hash_for_event(rows[0], GENESIS_HASH)
            assert rows[1].prev_hash == rows[0].row_hash

    asyncio.run(_run())


@pytest.mark.integration
def test_verify_chain_detects_tamper(api_up):
    async def _run() -> None:
        org_id = uuid.uuid4()
        user_id = uuid.uuid4()
        async with async_session_factory() as db:
            org = Organization(id=org_id, name="Tamper Org", slug=f"tamper-{uuid.uuid4().hex[:8]}")
            db.add(org)
            user = User(
                id=user_id,
                email=f"tamper-{uuid.uuid4().hex[:8]}@test.local",
                password_hash="x",
                org_id=org_id,
                role="owner",
            )
            db.add(user)
            await db.flush()
            await log_audit(db, user, "before", "matter")
            await log_audit(db, user, "after", "matter")
            await db.commit()

            ev = (
                await db.execute(select(AuditEvent).where(AuditEvent.org_id == org_id).limit(1))
            ).scalar_one()
            await db.execute(
                text("UPDATE audit_events SET action = :a WHERE id = :id"),
                {"a": "tampered", "id": ev.id},
            )
            await db.commit()

        async with async_session_factory() as verify_db:
            result = await verify_chain(verify_db, org_id=org_id)
            assert result["valid"] is False
            assert result["reason"] == "row_hash_mismatch"

    asyncio.run(_run())

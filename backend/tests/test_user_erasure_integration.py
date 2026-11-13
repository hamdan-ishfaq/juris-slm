"""Deleting a user who has used the product erases them without breaking the audit chain."""
from __future__ import annotations

import asyncio
import uuid

import pytest
from sqlalchemy import select, text

from api_helpers import api_request, login_user, register_user
from db import ChatThread, Matter, User, async_session_factory, engine


@pytest.mark.integration
def test_a_user_with_history_is_erased_and_the_audit_chain_still_verifies(api_up):
    owner = register_user(org_name=f"EraseOwner-{uuid.uuid4().hex[:6]}")
    member = register_user(org_name=f"EraseMember-{uuid.uuid4().hex[:6]}")

    async def move_member() -> None:
        async with async_session_factory() as db:
            await db.execute(
                text("UPDATE users SET org_id = :org, role = 'member' WHERE id = :id"),
                {"org": owner["org_id"], "id": member["user_id"]},
            )
            await db.commit()
        await engine.dispose()  # pooled connections belong to this event loop, which asyncio.run closes

    asyncio.run(move_member())
    token = login_user(member["email"], member["password"])
    matter = api_request("POST", "/api/v1/matters", token=token, json_body={"name": "member's matter"}).json()
    assert api_request("POST", "/api/v1/threads", token=token, json_body={"title": "member's chat"}).status_code == 200

    # Before the fix this was a 500: the member's audit events and threads blocked the delete.
    r = api_request("DELETE", f"/api/v1/admin/users/{member['user_id']}", token=owner["token"])
    assert r.status_code == 204, r.text

    async def state() -> tuple:
        async with async_session_factory() as db:
            user = await db.get(User, uuid.UUID(member["user_id"]))
            threads = (await db.execute(select(ChatThread).where(ChatThread.user_id == user.id))).scalars().all()
            owner_of_matter = (await db.get(Matter, uuid.UUID(matter["id"]))).user_id
            found = user.email, user.disabled_at, len(threads), str(owner_of_matter)
        await engine.dispose()
        return found

    email, disabled_at, threads, matter_owner = asyncio.run(state())
    assert email.startswith("deleted-") and disabled_at is not None
    assert threads == 0
    assert matter_owner == owner["user_id"]
    with pytest.raises(Exception):
        login_user(member["email"], member["password"])
    verify = api_request("GET", "/api/v1/audit/verify", token=owner["token"]).json()
    assert verify["valid"] is True, verify

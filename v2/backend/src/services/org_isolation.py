"""Phase 9A — organization isolation helpers."""
from __future__ import annotations

import uuid

from fastapi import HTTPException, status
from sqlalchemy import and_, or_, select

from db import Matter, User


def assert_org_access(user: User, resource_org_id: uuid.UUID | None) -> None:
    """Return 404 when user's org does not match resource org (avoid cross-tenant enumeration)."""
    if user.org_id is None:
        if resource_org_id is not None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Not found")
        return
    if resource_org_id is None or user.org_id != resource_org_id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Not found")


def assert_matter_org(user: User, matter: Matter) -> None:
    assert_org_access(user, matter.org_id)


def matter_access_filter(user: User):
    """SQLAlchemy filter clause: matters visible within user's organization."""
    if user.org_id is None:
        return True
    return Matter.org_id == user.org_id


def accessible_matter_predicate(user: User):
    """Combine membership with org boundary."""
    from db import MatterMember

    membership = or_(
        Matter.user_id == user.id,
        Matter.id.in_(select(MatterMember.matter_id).where(MatterMember.user_id == user.id)),
    )
    if user.org_id is None:
        return membership
    return and_(membership, Matter.org_id == user.org_id)

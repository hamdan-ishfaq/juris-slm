from __future__ import annotations

import uuid
from typing import Callable

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBearer
from sqlalchemy import or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from auth_utils import decode_token
from db import Matter, MatterDocument, MatterMember, User, get_db
from services.access_control import can_access_confidentiality, matter_role_at_least

security = HTTPBearer()


async def get_current_user(
    credentials=Depends(security),
    db: AsyncSession = Depends(get_db),
) -> User:
    try:
        payload = decode_token(credentials.credentials)
        user_id = payload.get("sub")
        if not user_id:
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token")
        user_id = uuid.UUID(user_id)
    except ValueError:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token")

    result = await db.execute(select(User).where(User.id == user_id))
    user = result.scalar_one_or_none()
    if not user:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="User not found")
    return user


def require_role(*roles: str) -> Callable:
    allowed = set(roles)

    async def _dep(user: User = Depends(get_current_user)) -> User:
        if user.role not in allowed:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Insufficient role")
        return user

    return _dep


async def get_matter_member_role(
    db: AsyncSession,
    matter_id: uuid.UUID,
    user_id: uuid.UUID,
) -> str | None:
    if await db.get(Matter, matter_id) is None:
        return None
    result = await db.execute(
        select(MatterMember.role).where(
            MatterMember.matter_id == matter_id,
            MatterMember.user_id == user_id,
        )
    )
    role = result.scalar_one_or_none()
    if role:
        return role
    matter = await db.get(Matter, matter_id)
    if matter and matter.user_id == user_id:
        return "owner"
    return None


async def require_matter_access(
    matter_id: uuid.UUID,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
    min_role: str = "viewer",
) -> Matter:
    matter = await db.get(Matter, matter_id)
    if not matter:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Matter not found")
    member_role = await get_matter_member_role(db, matter_id, user.id)
    if member_role is None or not matter_role_at_least(member_role, min_role):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Matter access denied")
    return matter


def require_matter_role(min_role: str = "viewer") -> Callable:
    async def _dep(
        matter_id: uuid.UUID,
        user: User = Depends(get_current_user),
        db: AsyncSession = Depends(get_db),
    ) -> Matter:
        return await require_matter_access(matter_id, user, db, min_role=min_role)

    return _dep


async def user_can_access_matter(db: AsyncSession, user: User, matter_id: uuid.UUID) -> bool:
    role = await get_matter_member_role(db, matter_id, user.id)
    return role is not None


async def get_accessible_document_ids(db: AsyncSession, user: User) -> set[uuid.UUID]:
    """Documents the user may retrieve via RAG (matter access + confidentiality)."""
    member_matters = select(MatterMember.matter_id).where(MatterMember.user_id == user.id)
    owned_matters = select(Matter.id).where(Matter.user_id == user.id)
    matter_ids_subq = member_matters.union(owned_matters)

    result = await db.execute(
        select(MatterDocument.id, MatterDocument.confidentiality).where(
            MatterDocument.matter_id.in_(matter_ids_subq)
        )
    )
    accessible: set[uuid.UUID] = set()
    for doc_id, confidentiality in result.all():
        if can_access_confidentiality(user.role, confidentiality):
            accessible.add(doc_id)
    return accessible


async def assert_document_accessible(
    db: AsyncSession,
    user: User,
    document_id: uuid.UUID,
) -> MatterDocument:
    doc = await db.get(MatterDocument, document_id)
    if not doc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Document not found")
    if not await user_can_access_matter(db, user, doc.matter_id):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Document not found")
    if not can_access_confidentiality(user.role, doc.confidentiality):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Document confidentiality denied")
    accessible = await get_accessible_document_ids(db, user)
    if document_id not in accessible:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Document not accessible")
    return doc


async def list_accessible_matters(db: AsyncSession, user: User) -> list[Matter]:
    result = await db.execute(
        select(Matter).where(
            or_(
                Matter.user_id == user.id,
                Matter.id.in_(select(MatterMember.matter_id).where(MatterMember.user_id == user.id)),
            )
        )
    )
    return list(result.scalars().all())

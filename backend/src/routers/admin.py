"""
routers/admin.py - Owner-only management endpoints
"""
from uuid import UUID
from typing import List

from fastapi import APIRouter, Depends, Header, HTTPException, status
from sqlalchemy import select, delete
from sqlalchemy.ext.asyncio import AsyncSession

from ..db import get_db, User, UserRole
from ..auth import get_current_user


router = APIRouter(prefix="/admin", tags=["admin"])


async def require_owner(
    authorization: str = Header(None),
    db: AsyncSession = Depends(get_db)
) -> User:
    if not authorization:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Missing authorization header")

    parts = authorization.split()
    if len(parts) != 2 or parts[0].lower() != "bearer":
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid authorization header format")

    token = parts[1]
    user = await get_current_user(token, db)
    if user.role != UserRole.OWNER:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Owner role required")
    return user


@router.get("/users")
async def list_users(
    current_owner: User = Depends(require_owner),
    db: AsyncSession = Depends(get_db)
) -> List[dict]:
    result = await db.execute(select(User))
    users = result.scalars().all()
    return [
        {
            "id": str(u.id),
            "email": u.email,
            "role": u.role.value,
            "created_at": u.created_at,
        }
        for u in users
    ]


@router.put("/users/{user_id}/role")
async def update_user_role(
    user_id: UUID,
    role: str,
    current_owner: User = Depends(require_owner),
    db: AsyncSession = Depends(get_db)
):
    role_norm = role.lower()
    if role_norm not in [UserRole.USER.value, UserRole.ADMIN.value]:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Role must be 'user' or 'admin'")

    result = await db.execute(select(User).where(User.id == user_id))
    target = result.scalar_one_or_none()
    if not target:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")

    if target.id == current_owner.id:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Cannot change your own role")

    target.role = UserRole(role_norm)
    await db.commit()
    await db.refresh(target)
    return {"id": str(target.id), "email": target.email, "role": target.role.value}


@router.delete("/users/{user_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_user(
    user_id: UUID,
    current_owner: User = Depends(require_owner),
    db: AsyncSession = Depends(get_db)
):
    if user_id == current_owner.id:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Cannot delete yourself")

    result = await db.execute(select(User).where(User.id == user_id))
    target = result.scalar_one_or_none()
    if not target:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")

    await db.execute(delete(User).where(User.id == user_id))
    await db.commit()
    return None

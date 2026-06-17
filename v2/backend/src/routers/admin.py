from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from db import User, get_db
from deps import require_role
from schemas import AdminRoleUpdateRequest, AdminUserResponse
from services.access_control import admin_role_at_least

router = APIRouter(prefix="/api/v1/admin", tags=["admin"])


@router.get("/users", response_model=list[AdminUserResponse])
async def list_users(
    user: User = Depends(require_role("org_admin", "owner")),
    db: AsyncSession = Depends(get_db),
):
    query = select(User)
    if user.org_id:
        query = query.where(User.org_id == user.org_id)
    result = await db.execute(query.order_by(User.created_at))
    return [
        AdminUserResponse(
            id=u.id,
            email=u.email,
            role=u.role,
            org_id=u.org_id,
            created_at=u.created_at,
        )
        for u in result.scalars().all()
    ]


@router.put("/users/{user_id}/role", response_model=AdminUserResponse)
async def update_user_role(
    user_id: UUID,
    body: AdminRoleUpdateRequest,
    actor: User = Depends(require_role("owner")),
    db: AsyncSession = Depends(get_db),
):
    target = await db.get(User, user_id)
    if not target:
        raise HTTPException(status_code=404, detail="User not found")
    if actor.org_id and target.org_id and actor.org_id != target.org_id:
        raise HTTPException(status_code=403, detail="Cannot modify users outside your organization")
    if target.id == actor.id:
        raise HTTPException(status_code=400, detail="Cannot change your own role")
    if body.role == "owner":
        raise HTTPException(status_code=400, detail="Owner role cannot be assigned via API")
    if not admin_role_at_least(body.role, "member"):
        raise HTTPException(status_code=400, detail="Invalid role")

    target.role = body.role
    await db.commit()
    await db.refresh(target)
    return AdminUserResponse(
        id=target.id,
        email=target.email,
        role=target.role,
        org_id=target.org_id,
        created_at=target.created_at,
    )


@router.delete("/users/{user_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_user(
    user_id: UUID,
    actor: User = Depends(require_role("owner")),
    db: AsyncSession = Depends(get_db),
):
    target = await db.get(User, user_id)
    if not target:
        raise HTTPException(status_code=404, detail="User not found")
    if actor.org_id and target.org_id and actor.org_id != target.org_id:
        raise HTTPException(status_code=403, detail="Cannot delete users outside your organization")
    if target.id == actor.id:
        raise HTTPException(status_code=400, detail="Cannot delete yourself")
    await db.delete(target)
    await db.commit()

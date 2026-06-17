import uuid

from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from auth_utils import create_access_token, hash_password, verify_password
from config import settings
from db import Organization, User, get_db, slugify_org_name
from deps import get_current_user
from rate_limit import limiter, rate_limit_exempt
from schemas import LoginRequest, RegisterRequest, TokenResponse, UserResponse
from services.dev_master import token_extra_for_user

router = APIRouter(prefix="/api/v1/auth", tags=["auth"])


def _user_response(user: User) -> UserResponse:
    return UserResponse(
        id=user.id,
        email=user.email,
        role=user.role,
        org_id=user.org_id,
        created_at=user.created_at,
    )


def _token_for_user(user: User) -> str:
    extra = {"role": user.role, "org_id": str(user.org_id) if user.org_id else None}
    extra.update(token_extra_for_user(user.email))
    return create_access_token(str(user.id), extra=extra)


async def _ensure_default_org(db: AsyncSession) -> Organization:
    result = await db.execute(select(Organization).where(Organization.slug == "default-org"))
    org = result.scalar_one_or_none()
    if org:
        return org
    org = Organization(name="Default Organization", slug="default-org")
    db.add(org)
    await db.flush()
    return org


@router.post("/register", response_model=TokenResponse, status_code=status.HTTP_201_CREATED)
@limiter.limit("15/minute", exempt_when=rate_limit_exempt)
async def register(request: Request, body: RegisterRequest, db: AsyncSession = Depends(get_db)):
    if not settings.registration_open:
        raise HTTPException(status.HTTP_403_FORBIDDEN, detail="Registration is disabled")
    existing = await db.execute(select(User).where(User.email == body.email.lower()))
    if existing.scalar_one_or_none():
        raise HTTPException(status.HTTP_409_CONFLICT, detail="Email already registered")
    try:
        pwd_hash = hash_password(body.password)
    except ValueError as exc:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc

    org: Organization | None = None
    role = "member"
    if body.org_name:
        base_slug = slugify_org_name(body.org_name)
        slug = base_slug
        suffix = 0
        while True:
            clash = await db.execute(select(Organization).where(Organization.slug == slug))
            if not clash.scalar_one_or_none():
                break
            suffix += 1
            slug = f"{base_slug}-{suffix}"[:64]
        org = Organization(id=uuid.uuid4(), name=body.org_name.strip(), slug=slug)
        db.add(org)
        await db.flush()
        role = "owner"
    else:
        org = await _ensure_default_org(db)

    user = User(
        email=body.email.lower(),
        password_hash=pwd_hash,
        role=role,
        org_id=org.id,
    )
    db.add(user)
    await db.commit()
    await db.refresh(user)
    token = _token_for_user(user)
    return TokenResponse(access_token=token, user=_user_response(user))


@router.post("/login", response_model=TokenResponse)
@limiter.limit("5/minute", exempt_when=rate_limit_exempt)
async def login(request: Request, body: LoginRequest, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(User).where(User.email == body.email.lower()))
    user = result.scalar_one_or_none()
    if user is None or not verify_password(body.password, user.password_hash):
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, detail="Invalid email or password")
    token = _token_for_user(user)
    return TokenResponse(access_token=token, user=_user_response(user))


@router.get("/me", response_model=UserResponse)
async def me(user: User = Depends(get_current_user)):
    return _user_response(user)

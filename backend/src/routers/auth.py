"""
routers/auth.py - Authentication endpoints
Handles user registration, login, and profile retrieval
"""
from fastapi import APIRouter, HTTPException, Depends, Header, status, Request
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.exc import IntegrityError
from slowapi import Limiter
from slowapi.util import get_remote_address

from ..db import get_db, User
from ..auth import (
    UserCreate,
    UserLogin,
    Token,
    UserResponse,
    verify_password,
    get_password_hash,
    create_access_token,
    get_current_user,
)

router = APIRouter(prefix="/auth", tags=["authentication"])

# Initialize limiter for auth endpoints
limiter = Limiter(key_func=get_remote_address)


@router.post("/register", status_code=status.HTTP_201_CREATED)
async def register(user_data: UserCreate, db: AsyncSession = Depends(get_db)) -> dict:
    """
    Register a new user
    
    Args:
        user_data: User registration data (email, password)
        db: Async database session
        
    Returns:
        JSON with user ID and email
        
    Raises:
        HTTPException 400: If email already exists
        HTTPException 500: If database error occurs
    """
    # Check if email already exists
    result = await db.execute(select(User).where(User.email == user_data.email))
    existing_user = result.scalar_one_or_none()
    
    if existing_user:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Email already registered"
        )
    
    # Hash password and create user
    try:
        hashed_password = get_password_hash(user_data.password)
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )
    
    new_user = User(email=user_data.email, password_hash=hashed_password)
    
    try:
        db.add(new_user)
        await db.commit()
        await db.refresh(new_user)
    except IntegrityError:
        await db.rollback()
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Failed to create user. Email may already exist."
        )
    except Exception as e:
        await db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Database error: {str(e)}"
        )
    
    return {
        "id": str(new_user.id),
        "email": new_user.email,
        "message": "User registered successfully"
    }


@router.post("/login", response_model=Token)
@limiter.limit("5/minute")
async def login(request: Request, credentials: UserLogin, db: AsyncSession = Depends(get_db)) -> dict:
    """
    Login user and return JWT access token
    
    Args:
        request: FastAPI request object (for rate limiting)
        credentials: User login credentials (email, password)
        db: Async database session
        
    Returns:
        JSON with access_token and token_type
        
    Raises:
        HTTPException 401: If credentials are invalid
    """
    # Find user by email
    result = await db.execute(select(User).where(User.email == credentials.email))
    user = result.scalar_one_or_none()
    
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid email or password",
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    # Verify password
    if not verify_password(credentials.password, user.password_hash):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid email or password",
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    # Create JWT token
    access_token = create_access_token(data={"sub": str(user.id), "role": user.role.value})
    
    return {
        "access_token": access_token,
        "token_type": "bearer"
    }


@router.get("/me", response_model=UserResponse)
async def get_me(
    authorization: str = Header(None),
    db: AsyncSession = Depends(get_db)
) -> UserResponse:
    """
    Get current authenticated user's profile
    
    Args:
        authorization: Bearer token from Authorization header (format: "Bearer <token>")
        db: Async database session
        
    Returns:
        UserResponse with user details (excludes password)
        
    Raises:
        HTTPException 401: If token is missing, invalid, or user not found
    """
    if not authorization:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing authorization header",
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    # Extract token from "Bearer <token>" format
    parts = authorization.split()
    if len(parts) != 2 or parts[0].lower() != "bearer":
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid authorization header format",
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    token = parts[1]
    
    try:
        user = await get_current_user(token, db)
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=str(e),
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    return UserResponse(
        id=str(user.id),
        email=user.email,
        role=user.role.value,
        created_at=user.created_at
    )

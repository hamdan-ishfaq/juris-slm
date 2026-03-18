"""
auth.py - Authentication and JWT token management
Secure password hashing, JWT creation/verification, and user dependency injection
"""
from datetime import datetime, timedelta, timezone
from typing import Optional

from jose import JWTError, jwt
from passlib.context import CryptContext
from pydantic import BaseModel, field_validator
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from .db import User

# Password hashing configuration
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

# JWT configuration (will be loaded from config)
SECRET_KEY: Optional[str] = None
ALGORITHM: str = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES: int = 60


def set_auth_config(secret_key: str, algorithm: str = "HS256", expire_minutes: int = 60) -> None:
    """
    Initialize authentication configuration
    
    Args:
        secret_key: Secret key for JWT signing
        algorithm: JWT algorithm (default: HS256)
        expire_minutes: Token expiration time in minutes
    """
    global SECRET_KEY, ALGORITHM, ACCESS_TOKEN_EXPIRE_MINUTES
    SECRET_KEY = secret_key
    ALGORITHM = algorithm
    ACCESS_TOKEN_EXPIRE_MINUTES = expire_minutes


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """
    Verify a plain password against its hash
    
    Args:
        plain_password: Plain text password to verify
        hashed_password: Hashed password from database
        
    Returns:
        True if password matches, False otherwise
    """
    return pwd_context.verify(plain_password, hashed_password)


def get_password_hash(password: str) -> str:
    """
    Hash a plain password using bcrypt
    
    Args:
        password: Plain text password to hash
        
    Returns:
        Bcrypt hash of the password
        
    Raises:
        ValueError: If password exceeds bcrypt's 72-byte limit
    """
    # Bcrypt has a hard 72-byte limit
    if len(password.encode('utf-8')) > 72:
        raise ValueError('Password cannot exceed 72 bytes')
    return pwd_context.hash(password)


def create_access_token(data: dict, expires_delta: Optional[timedelta] = None) -> str:
    """
    Create a JWT access token
    
    Args:
        data: Dictionary containing claims (should include 'sub' for user_id)
        expires_delta: Optional custom expiration time; uses ACCESS_TOKEN_EXPIRE_MINUTES if None
        
    Returns:
        Encoded JWT token as string
        
    Raises:
        RuntimeError: If SECRET_KEY is not initialized
    """
    if SECRET_KEY is None:
        raise RuntimeError("AUTH_SECRET_KEY not configured. Call set_auth_config() first.")
    
    to_encode = data.copy()
    if expires_delta:
        expire = datetime.now(timezone.utc) + expires_delta
    else:
        expire = datetime.now(timezone.utc) + timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    
    to_encode.update({"exp": expire})
    encoded_jwt = jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)
    return encoded_jwt


async def get_current_user(token: str, db: AsyncSession) -> User:
    """
    Decode JWT token and retrieve the current user from database
    
    Args:
        token: JWT access token
        db: Async database session
        
    Returns:
        User object if token is valid and user exists
        
    Raises:
        ValueError: If token is invalid or user not found
    """
    if SECRET_KEY is None:
        raise RuntimeError("AUTH_SECRET_KEY not configured.")
    
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        user_id: str = payload.get("sub")
        
        if user_id is None:
            raise ValueError("Invalid token: missing user_id")
    except JWTError as e:
        raise ValueError(f"Invalid token: {str(e)}")
    
    # Query database asynchronously
    result = await db.execute(select(User).where(User.id == user_id))
    user = result.scalar_one_or_none()
    
    if user is None:
        raise ValueError("User not found")
    
    return user


# Pydantic models for API schemas
class UserCreate(BaseModel):
    """Schema for user registration"""
    email: str
    password: str
    
    @field_validator('password')
    @classmethod
    def validate_password(cls, v):
        """Validate password length (bcrypt limit: 72 bytes)"""
        if len(v.encode('utf-8')) > 72:
            raise ValueError('Password cannot exceed 72 bytes')
        if len(v) < 8:
            raise ValueError('Password must be at least 8 characters')
        return v
    
    class Config:
        json_schema_extra = {
            "example": {
                "email": "user@example.com",
                "password": "secure_password_123"
            }
        }


class UserLogin(BaseModel):
    """Schema for user login (compatible with OAuth2PasswordRequestForm)"""
    email: str
    password: str
    
    class Config:
        json_schema_extra = {
            "example": {
                "email": "user@example.com",
                "password": "secure_password_123"
            }
        }


class Token(BaseModel):
    """Schema for JWT token response"""
    access_token: str
    token_type: str
    
    class Config:
        json_schema_extra = {
            "example": {
                "access_token": "eyJ0eXAiOiJKV1QiLCJhbGciOiJIUzI1NiJ9...",
                "token_type": "bearer"
            }
        }


class UserResponse(BaseModel):
    """Schema for user data response (excludes password)"""
    id: str
    email: str
    role: str
    created_at: datetime
    
    class Config:
        json_schema_extra = {
            "example": {
                "id": "550e8400-e29b-41d4-a716-446655440000",
                "email": "user@example.com",
                "role": "user",
                "created_at": "2025-01-17T10:30:00Z"
            }
        }

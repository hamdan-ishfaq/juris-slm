from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, EmailStr, Field


class RegisterRequest(BaseModel):
    email: EmailStr
    password: str = Field(min_length=8, max_length=128)


class LoginRequest(BaseModel):
    email: EmailStr
    password: str


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"


class UserResponse(BaseModel):
    id: UUID
    email: str
    created_at: datetime


class ChatRequest(BaseModel):
    message: str = Field(min_length=1, max_length=8000)
    use_law_corpus: bool = True


class ChatResponse(BaseModel):
    answer: str
    model: str
    sources: list[dict]


class CorpusStatsResponse(BaseModel):
    total_chunks: int
    by_source: dict[str, int]

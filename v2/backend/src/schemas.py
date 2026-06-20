from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, EmailStr, Field


class RegisterRequest(BaseModel):
    email: EmailStr
    password: str = Field(min_length=8, max_length=128)
    org_name: str | None = Field(default=None, max_length=255)


class LoginRequest(BaseModel):
    email: EmailStr
    password: str


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    refresh_token: str | None = None
    user: "UserResponse | None" = None


class RefreshRequest(BaseModel):
    refresh_token: str = Field(min_length=10)


class UserResponse(BaseModel):
    id: UUID
    email: str
    role: str = "member"
    org_id: UUID | None = None
    created_at: datetime


class ChatRequest(BaseModel):
    message: str = Field(min_length=1, max_length=8000)
    use_law_corpus: bool = True
    use_hyde: bool = False
    thread_id: UUID | None = None


class ChatResponse(BaseModel):
    answer: str
    model: str
    sources: list[dict]
    thread_id: UUID | None = None
    cached: bool = False


class ChatJobResponse(BaseModel):
    job_id: str
    status: str


class ChatJobStatusResponse(BaseModel):
    job_id: str
    status: str
    progress_step: str | None = None
    answer: str | None = None
    model: str | None = None
    sources: list[dict] | None = None
    thread_id: UUID | None = None
    error: str | None = None


class CorpusStatsResponse(BaseModel):
    total_chunks: int
    by_source: dict[str, int]


class MemberInviteRequest(BaseModel):
    email: EmailStr
    role: str = Field(default="viewer", pattern="^(viewer|editor|owner)$")


class MemberResponse(BaseModel):
    matter_id: UUID
    user_id: UUID
    email: str
    role: str
    invited_at: datetime


class AdminUserResponse(BaseModel):
    id: UUID
    email: str
    role: str
    org_id: UUID | None
    created_at: datetime


class AdminRoleUpdateRequest(BaseModel):
    role: str = Field(pattern="^(member|matter_lead|org_admin|owner)$")


class AuditEventResponse(BaseModel):
    id: UUID
    user_id: UUID
    org_id: UUID | None
    action: str
    resource_type: str
    resource_id: str | None
    timestamp: datetime
    details: dict | None = None


class AuditListResponse(BaseModel):
    items: list[AuditEventResponse]
    total: int
    page: int
    page_size: int


TokenResponse.model_rebuild()

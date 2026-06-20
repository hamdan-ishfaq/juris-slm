"""Phase 9F — contract workspace API schemas."""
from __future__ import annotations

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, Field


class ClauseItem(BaseModel):
    id: str
    title: str
    start: int
    end: int
    text: str


class DocumentVersionResponse(BaseModel):
    id: UUID
    version_number: int
    content_text: str
    clauses: list[ClauseItem]
    diff_hash: str | None = None
    created_by: UUID | None = None
    created_at: datetime
    read_only: bool = False


class WorkspaceSaveRequest(BaseModel):
    content_text: str = Field(min_length=1)
    expected_version_number: int | None = None


class ClauseAnnotationCreate(BaseModel):
    clause_id: str = Field(min_length=1, max_length=64)
    comment: str = Field(min_length=1, max_length=4000)


class ClauseAnnotationResponse(BaseModel):
    id: UUID
    document_id: UUID
    version_id: UUID | None
    clause_id: str
    comment: str
    created_by: UUID | None
    created_at: datetime

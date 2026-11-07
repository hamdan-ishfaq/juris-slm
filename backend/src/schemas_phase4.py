from pydantic import BaseModel
from datetime import date, datetime
from uuid import UUID
from typing import Optional

class MatterCreate(BaseModel):
    name: str
    description: Optional[str] = None

class MatterResponse(BaseModel):
    id: UUID
    user_id: UUID
    name: str
    description: Optional[str]
    created_at: datetime

class MatterDocumentCreate(BaseModel):
    filename: str
    file_path: str

class MatterDocumentResponse(BaseModel):
    id: UUID
    matter_id: UUID
    filename: str
    file_path: str
    uploaded_at: datetime

class AuditEventResponse(BaseModel):
    id: UUID
    user_id: UUID
    action: str
    resource_type: str
    resource_id: Optional[str]
    timestamp: datetime
    details: Optional[dict] = None

class DocumentUploadResponse(BaseModel):
    id: UUID
    matter_id: UUID
    filename: str
    file_path: str
    uploaded_at: datetime
    ingest_status: str = "pending"
    ingest_error: str | None = None
    ocr_used: bool = False


class DocumentStatusResponse(BaseModel):
    status: str
    ocr_used: bool = False
    error: str | None = None


class DocumentCompareClauseRequest(BaseModel):
    document_id: UUID
    clause_library_id: UUID
    question: str | None = None


class DocumentCompareClauseResponse(BaseModel):
    document_id: UUID
    clause_library_id: UUID
    comparison_result: str
    model: str
    deviation_flag: str
    sources: list[dict] = []


class MatterDeadlineCreate(BaseModel):
    title: str
    due_date: date
    notes: str | None = None


class MatterDeadlineUpdate(BaseModel):
    title: str | None = None
    due_date: date | None = None
    status: str | None = None
    notes: str | None = None


class MatterDeadlineResponse(BaseModel):
    id: UUID
    matter_id: UUID
    title: str
    due_date: date
    status: str
    notes: str | None = None
    created_at: datetime

class DocumentAnalysisRequest(BaseModel):
    document_id: UUID
    question: str

class DocumentAnalysisResponse(BaseModel):
    document_id: UUID
    question: str
    answer: str
    model: str
    sources: list[dict]
    structured: Optional[dict] = None
    risk: Optional[dict] = None
    playbook: Optional[list] = None

class DocumentCompareRequest(BaseModel):
    document_id: UUID

class DocumentCompareResponse(BaseModel):
    document_id: UUID
    comparison_result: str
    model: str

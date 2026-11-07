from pydantic import BaseModel
from datetime import datetime
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


class DocumentAnalysisRequest(BaseModel):
    document_id: UUID
    question: str
    skip_cache: bool = False

class DocumentAnalysisResponse(BaseModel):
    document_id: UUID
    question: str
    answer: str
    model: str
    sources: list[dict]
    answer_mode: str = "llm"
    timings_ms: dict[str, float] = {}
    structured: Optional[dict] = None
    risk: Optional[dict] = None
    playbook: Optional[list] = None

class DocumentCompareRequest(BaseModel):
    document_id: UUID

class DocumentCompareResponse(BaseModel):
    document_id: UUID
    comparison_result: str
    model: str

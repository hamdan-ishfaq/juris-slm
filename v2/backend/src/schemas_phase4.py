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

class DocumentAnalysisRequest(BaseModel):
    document_id: UUID
    question: str

class DocumentAnalysisResponse(BaseModel):
    document_id: UUID
    question: str
    answer: str
    model: str
    sources: list[dict]

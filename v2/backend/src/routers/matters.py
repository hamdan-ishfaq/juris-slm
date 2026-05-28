from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from uuid import UUID
import uuid
from datetime import datetime, timezone
from db import Matter, MatterDocument, AuditEvent, get_db
from schemas_phase4 import MatterCreate, MatterResponse, MatterDocumentResponse, DocumentUploadResponse, DocumentAnalysisRequest, DocumentAnalysisResponse
from deps import get_current_user

router = APIRouter(prefix="/api/v1/matters", tags=["matters"])

@router.post("", response_model=MatterResponse)
async def create_matter(
    req: MatterCreate,
    user = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    matter = Matter(
        id=uuid.uuid4(),
        user_id=user.id,
        name=req.name,
        description=req.description
    )
    db.add(matter)
    
    # Audit log
    audit = AuditEvent(
        id=uuid.uuid4(),
        user_id=user.id,
        action="create",
        resource_type="matter",
        resource_id=str(matter.id),
        timestamp=datetime.now(timezone.utc),
        details={"name": req.name}
    )
    db.add(audit)
    await db.commit()
    return matter

@router.get("", response_model=list[MatterResponse])
async def list_matters(
    user = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    result = await db.execute(select(Matter).where(Matter.user_id == user.id))
    return result.scalars().all()

@router.get("/{matter_id}", response_model=MatterResponse)
async def get_matter(
    matter_id: UUID,
    user = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    result = await db.execute(select(Matter).where(Matter.id == matter_id, Matter.user_id == user.id))
    matter = result.scalar_one_or_none()
    if not matter:
        raise HTTPException(status_code=404, detail="Matter not found")
    return matter

@router.delete("/{matter_id}")
async def delete_matter(
    matter_id: UUID,
    user = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    result = await db.execute(select(Matter).where(Matter.id == matter_id, Matter.user_id == user.id))
    matter = result.scalar_one_or_none()
    if not matter:
        raise HTTPException(status_code=404, detail="Matter not found")
    
    await db.delete(matter)
    
    audit = AuditEvent(
        id=uuid.uuid4(),
        user_id=user.id,
        action="delete",
        resource_type="matter",
        resource_id=str(matter.id),
        timestamp=datetime.now(timezone.utc)
    )
    db.add(audit)
    await db.commit()
    return {"ok": True}

from fastapi import File, UploadFile
import aiofiles
from pathlib import Path

UPLOAD_DIR = Path("/app/data/uploads")

@router.post("/{matter_id}/documents", response_model=DocumentUploadResponse)
async def upload_document(
    matter_id: UUID,
    file: UploadFile = File(...),
    user = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    # Verify matter belongs to user
    result = await db.execute(select(Matter).where(Matter.id == matter_id, Matter.user_id == user.id))
    matter = result.scalar_one_or_none()
    if not matter:
        raise HTTPException(status_code=404, detail="Matter not found")
    
    # Create uploads dir if needed
    UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
    
    # Save file
    file_path = UPLOAD_DIR / f"{matter_id}/{file.filename}"
    file_path.parent.mkdir(parents=True, exist_ok=True)
    
    async with aiofiles.open(file_path, "wb") as f:
        await f.write(await file.read())
    
    # Record in DB
    doc = MatterDocument(
        id=uuid.uuid4(),
        matter_id=matter_id,
        filename=file.filename,
        file_path=str(file_path)
    )
    db.add(doc)
    
    # Audit
    audit = AuditEvent(
        id=uuid.uuid4(),
        user_id=user.id,
        action="upload",
        resource_type="document",
        resource_id=str(doc.id),
        timestamp=datetime.now(timezone.utc),
        details={"filename": file.filename, "matter_id": str(matter_id)}
    )
    db.add(audit)
    await db.commit()
    
    return doc

@router.post("/{matter_id}/analyze", response_model=DocumentAnalysisResponse)
async def analyze_document(
    matter_id: UUID,
    req: DocumentAnalysisRequest,
    user = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    from services.rag import answer_question
    
    # Verify matter belongs to user
    result = await db.execute(select(Matter).where(Matter.id == matter_id, Matter.user_id == user.id))
    matter = result.scalar_one_or_none()
    if not matter:
        raise HTTPException(status_code=404, detail="Matter not found")
    
    # Verify document belongs to matter
    result = await db.execute(select(MatterDocument).where(MatterDocument.id == req.document_id, MatterDocument.matter_id == matter_id))
    doc = result.scalar_one_or_none()
    if not doc:
        raise HTTPException(status_code=404, detail="Document not found")
    
    # Run RAG
    rag_result = await answer_question(db, req.question, use_law_corpus=True)
    
    # Audit
    audit = AuditEvent(
        id=uuid.uuid4(),
        user_id=user.id,
        action="analyze",
        resource_type="document",
        resource_id=str(req.document_id),
        timestamp=datetime.now(timezone.utc),
        details={"question": req.question, "matter_id": str(matter_id)}
    )
    db.add(audit)
    await db.commit()
    
    return DocumentAnalysisResponse(
        document_id=req.document_id,
        question=req.question,
        answer=rag_result["answer"],
        model=rag_result["model"],
        sources=rag_result["sources"]
    )

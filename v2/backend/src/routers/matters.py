from fastapi import APIRouter, Depends, HTTPException, File, UploadFile
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func
from uuid import UUID
import uuid
from datetime import datetime, timezone
import aiofiles
from pathlib import Path

from db import Matter, MatterDocument, AuditEvent, DocumentChunk, GraphNode, GraphEdge, get_db
from schemas_phase4 import (
    MatterCreate, MatterResponse, MatterDocumentResponse, DocumentUploadResponse, 
    DocumentAnalysisRequest, DocumentAnalysisResponse, DocumentCompareRequest, DocumentCompareResponse
)
from deps import get_current_user
import logging

logger = logging.getLogger(__name__)

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
    
    from sqlalchemy import delete as sa_delete
    
    # Get all document IDs for this matter
    doc_result = await db.execute(select(MatterDocument.id).where(MatterDocument.matter_id == matter_id))
    doc_ids = doc_result.scalars().all()
    
    if doc_ids:
        # Get all node IDs under these documents
        node_result = await db.execute(select(GraphNode.id).where(GraphNode.document_id.in_(doc_ids)))
        node_ids = node_result.scalars().all()
        
        if node_ids:
            # Delete GraphEdges referencing these nodes
            await db.execute(sa_delete(GraphEdge).where(
                (GraphEdge.source_node_id.in_(node_ids)) | (GraphEdge.target_node_id.in_(node_ids))
            ))
            # Delete GraphNodes
            await db.execute(sa_delete(GraphNode).where(GraphNode.id.in_(node_ids)))
            
        # Delete DocumentChunks
        await db.execute(sa_delete(DocumentChunk).where(DocumentChunk.document_id.in_(doc_ids)))
        
        # Delete MatterDocuments
        await db.execute(sa_delete(MatterDocument).where(MatterDocument.id.in_(doc_ids)))
    
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

UPLOAD_DIR = Path(__file__).resolve().parent.parent / "data" / "uploads"

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
    
    UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
    
    file_path = UPLOAD_DIR / f"{matter_id}/{file.filename}"
    file_path.parent.mkdir(parents=True, exist_ok=True)
    
    async with aiofiles.open(file_path, "wb") as f:
        await f.write(await file.read())
    
    doc = MatterDocument(
        id=uuid.uuid4(),
        matter_id=matter_id,
        filename=file.filename,
        file_path=str(file_path)
    )
    db.add(doc)
    
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
    
    # Trigger Async processing
    try:
        from worker import process_document_task

        process_document_task.delay(str(doc.id))
    except Exception as e:
        logger.warning("Could not trigger celery task: %s", e)
    
    return doc

@router.get("/{matter_id}/documents/{document_id}/status")
async def get_document_status(
    matter_id: UUID,
    document_id: UUID,
    user = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    # Verify access
    result = await db.execute(select(MatterDocument).join(Matter).where(MatterDocument.id == document_id, Matter.id == matter_id, Matter.user_id == user.id))
    if not result.scalar_one_or_none():
        raise HTTPException(status_code=404, detail="Document not found")
        
    # Check if chunks exist
    count_res = await db.execute(select(func.count(DocumentChunk.id)).where(DocumentChunk.document_id == document_id))
    if count_res.scalar_one() > 0:
        return {"status": "processed"}
    return {"status": "processing"}

@router.get("/{matter_id}/documents/{document_id}/graph-entities")
async def get_graph_entities(
    matter_id: UUID,
    document_id: UUID,
    user = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    result = await db.execute(select(MatterDocument).join(Matter).where(MatterDocument.id == document_id, Matter.id == matter_id, Matter.user_id == user.id))
    if not result.scalar_one_or_none():
        raise HTTPException(status_code=404, detail="Document not found")
        
    nodes = await db.execute(select(GraphNode).where(GraphNode.document_id == document_id))
    entities = [{"id": str(n.id), "name": n.name, "type": n.type, "description": n.description} for n in nodes.scalars().all()]
    return {"entities": entities}

@router.get("/{matter_id}/documents/{document_id}/graph-edges")
async def get_graph_edges(
    matter_id: UUID,
    document_id: UUID,
    user = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    result = await db.execute(select(MatterDocument).join(Matter).where(MatterDocument.id == document_id, Matter.id == matter_id, Matter.user_id == user.id))
    if not result.scalar_one_or_none():
        raise HTTPException(status_code=404, detail="Document not found")
        
    edges_res = await db.execute(
        select(GraphEdge)
        .join(GraphNode, GraphEdge.source_node_id == GraphNode.id)
        .where(GraphNode.document_id == document_id)
    )
    edges = [{"id": str(e.id), "source": str(e.source_node_id), "target": str(e.target_node_id), "type": e.relationship} for e in edges_res.scalars().all()]
    return {"edges": edges}

@router.post("/{matter_id}/analyze", response_model=DocumentAnalysisResponse)
async def analyze_document(
    matter_id: UUID,
    req: DocumentAnalysisRequest,
    user = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    from services.rag import answer_question
    
    result = await db.execute(select(Matter).where(Matter.id == matter_id, Matter.user_id == user.id))
    matter = result.scalar_one_or_none()
    if not matter:
        raise HTTPException(status_code=404, detail="Matter not found")
    
    result = await db.execute(select(MatterDocument).where(MatterDocument.id == req.document_id, MatterDocument.matter_id == matter_id))
    doc = result.scalar_one_or_none()
    if not doc:
        raise HTTPException(status_code=404, detail="Document not found")
    
    # Run RAG restricted to this document
    rag_result = await answer_question(db, req.question, use_law_corpus=False, document_id=str(req.document_id))
    
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

@router.post("/{matter_id}/compare", response_model=DocumentCompareResponse)
async def compare_document(
    matter_id: UUID,
    req: DocumentCompareRequest,
    user = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    from services.rag import answer_question
    
    result = await db.execute(select(Matter).where(Matter.id == matter_id, Matter.user_id == user.id))
    matter = result.scalar_one_or_none()
    if not matter:
        raise HTTPException(status_code=404, detail="Matter not found")
    
    result = await db.execute(select(MatterDocument).where(MatterDocument.id == req.document_id, MatterDocument.matter_id == matter_id))
    doc = result.scalar_one_or_none()
    if not doc:
        raise HTTPException(status_code=404, detail="Document not found")
    
    # Compare document against GDPR/BGB baseline and matter-scoped contract chunks
    comparison_question = (
        f"Compare the uploaded document ({doc.filename}) against the GDPR and BGB baseline. "
        "Identify material deviations or non-compliance risks."
    )
    rag_doc = await answer_question(db, comparison_question, use_law_corpus=False, document_id=str(req.document_id))
    try:
        rag_law = await answer_question(db, comparison_question, use_law_corpus=True)
    except RuntimeError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    combined = (
        f"## Document analysis\n{rag_doc['answer']}\n\n## Regulatory baseline (GDPR/BGB)\n{rag_law['answer']}"
    )
    
    audit = AuditEvent(
        id=uuid.uuid4(),
        user_id=user.id,
        action="compare",
        resource_type="document",
        resource_id=str(req.document_id),
        timestamp=datetime.now(timezone.utc),
        details={"matter_id": str(matter_id)}
    )
    db.add(audit)
    await db.commit()
    
    return DocumentCompareResponse(
        document_id=req.document_id,
        comparison_result=combined,
        model=rag_law["model"]
    )

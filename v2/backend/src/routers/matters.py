from __future__ import annotations

import logging
import uuid
from datetime import datetime, timezone
from pathlib import Path
from uuid import UUID

import aiofiles
from fastapi import APIRouter, Depends, File, Form, HTTPException, Request, UploadFile
from sqlalchemy import delete as sa_delete, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from db import AuditEvent, DocumentChunk, GraphEdge, GraphNode, Matter, MatterDocument, MatterMember, User, get_db
from deps import (
    assert_document_accessible,
    get_current_user,
    list_accessible_matters,
    require_matter_access,
    user_can_access_matter,
)
from rate_limit import limiter, rate_limit_exempt
from schemas import MemberInviteRequest, MemberResponse
from schemas_phase4 import (
    DocumentAnalysisRequest,
    DocumentAnalysisResponse,
    DocumentCompareRequest,
    DocumentCompareResponse,
    DocumentUploadResponse,
    MatterCreate,
    MatterResponse,
)
from services.access_control import can_upload_confidentiality
from services.upload_security import read_upload_bounded, safe_upload_filename

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/matters", tags=["matters"])

UPLOAD_DIR = Path(__file__).resolve().parent.parent / "data" / "uploads"
VALID_CONFIDENTIALITY = frozenset({"internal", "restricted", "privileged"})
VALID_MEMBER_ROLES = frozenset({"viewer", "editor", "owner"})


def _audit(user: User, action: str, resource_type: str, resource_id: str | None, details: dict | None = None) -> AuditEvent:
    return AuditEvent(
        id=uuid.uuid4(),
        user_id=user.id,
        org_id=user.org_id,
        action=action,
        resource_type=resource_type,
        resource_id=resource_id,
        timestamp=datetime.now(timezone.utc),
        details=details,
    )


@router.post("", response_model=MatterResponse)
async def create_matter(
    req: MatterCreate,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    matter = Matter(
        id=uuid.uuid4(),
        user_id=user.id,
        org_id=user.org_id,
        name=req.name,
        description=req.description,
    )
    db.add(matter)
    db.add(MatterMember(matter_id=matter.id, user_id=user.id, role="owner", invited_by=user.id))
    db.add(_audit(user, "create", "matter", str(matter.id), {"name": req.name}))
    await db.commit()
    await db.refresh(matter)
    return matter


@router.get("", response_model=list[MatterResponse])
async def list_matters(
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    return await list_accessible_matters(db, user)


@router.get("/{matter_id}", response_model=MatterResponse)
async def get_matter(
    matter_id: UUID,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    await require_matter_access(matter_id, user, db, min_role="viewer")
    matter = await db.get(Matter, matter_id)
    return matter


@router.delete("/{matter_id}")
async def delete_matter(
    matter_id: UUID,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    await require_matter_access(matter_id, user, db, min_role="owner")
    matter = await db.get(Matter, matter_id)
    if not matter:
        raise HTTPException(status_code=404, detail="Matter not found")

    doc_result = await db.execute(select(MatterDocument.id).where(MatterDocument.matter_id == matter_id))
    doc_ids = doc_result.scalars().all()

    if doc_ids:
        node_result = await db.execute(select(GraphNode.id).where(GraphNode.document_id.in_(doc_ids)))
        node_ids = node_result.scalars().all()
        if node_ids:
            await db.execute(
                sa_delete(GraphEdge).where(
                    (GraphEdge.source_node_id.in_(node_ids)) | (GraphEdge.target_node_id.in_(node_ids))
                )
            )
            await db.execute(sa_delete(GraphNode).where(GraphNode.id.in_(node_ids)))
        await db.execute(sa_delete(DocumentChunk).where(DocumentChunk.document_id.in_(doc_ids)))
        await db.execute(sa_delete(MatterDocument).where(MatterDocument.id.in_(doc_ids)))
        await db.execute(sa_delete(MatterMember).where(MatterMember.matter_id == matter_id))

    await db.delete(matter)
    db.add(_audit(user, "delete", "matter", str(matter_id)))
    await db.commit()
    return {"ok": True}


@router.post("/{matter_id}/members", response_model=MemberResponse)
async def invite_member(
    matter_id: UUID,
    body: MemberInviteRequest,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    await require_matter_access(matter_id, user, db, min_role="owner")
    if body.role not in VALID_MEMBER_ROLES:
        raise HTTPException(status_code=400, detail="Invalid member role")

    target_res = await db.execute(select(User).where(User.email == body.email.lower()))
    target = target_res.scalar_one_or_none()
    if not target:
        raise HTTPException(status_code=404, detail="User not found")
    if user.org_id and target.org_id and user.org_id != target.org_id:
        raise HTTPException(status_code=400, detail="User must belong to the same organization")

    existing = await db.execute(
        select(MatterMember).where(MatterMember.matter_id == matter_id, MatterMember.user_id == target.id)
    )
    if existing.scalar_one_or_none():
        raise HTTPException(status_code=409, detail="User is already a member")

    member = MatterMember(
        matter_id=matter_id,
        user_id=target.id,
        role=body.role,
        invited_by=user.id,
    )
    db.add(member)
    db.add(_audit(user, "invite_member", "matter", str(matter_id), {"user_id": str(target.id), "role": body.role}))
    await db.commit()
    return MemberResponse(
        matter_id=matter_id,
        user_id=target.id,
        email=target.email,
        role=body.role,
        invited_at=member.invited_at,
    )


@router.delete("/{matter_id}/members/{member_user_id}")
async def remove_member(
    matter_id: UUID,
    member_user_id: UUID,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    await require_matter_access(matter_id, user, db, min_role="owner")
    matter = await db.get(Matter, matter_id)
    if matter and matter.user_id == member_user_id:
        raise HTTPException(status_code=400, detail="Cannot remove matter creator")

    result = await db.execute(
        select(MatterMember).where(MatterMember.matter_id == matter_id, MatterMember.user_id == member_user_id)
    )
    member = result.scalar_one_or_none()
    if not member:
        raise HTTPException(status_code=404, detail="Member not found")
    await db.delete(member)
    db.add(_audit(user, "remove_member", "matter", str(matter_id), {"user_id": str(member_user_id)}))
    await db.commit()
    return {"ok": True}


@router.post("/{matter_id}/documents", response_model=DocumentUploadResponse)
@limiter.limit("5/hour", exempt_when=rate_limit_exempt)
async def upload_document(
    request: Request,
    matter_id: UUID,
    file: UploadFile = File(...),
    confidentiality: str = Form(default="internal"),
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    await require_matter_access(matter_id, user, db, min_role="editor")
    level = confidentiality.lower().strip()
    if level not in VALID_CONFIDENTIALITY:
        raise HTTPException(status_code=400, detail="Invalid confidentiality level")
    if not can_upload_confidentiality(user.role, level):
        raise HTTPException(status_code=403, detail=f"Cannot upload {level} documents with role {user.role}")

    safe_name = safe_upload_filename(file.filename)
    UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
    file_path = UPLOAD_DIR / f"{matter_id}/{safe_name}"
    file_path.parent.mkdir(parents=True, exist_ok=True)

    payload = await read_upload_bounded(file)
    async with aiofiles.open(file_path, "wb") as f:
        await f.write(payload)

    doc = MatterDocument(
        id=uuid.uuid4(),
        matter_id=matter_id,
        filename=safe_name,
        file_path=str(file_path),
        confidentiality=level,
    )
    db.add(doc)
    db.add(
        _audit(
            user,
            "upload",
            "document",
            str(doc.id),
            {"filename": safe_name, "matter_id": str(matter_id), "confidentiality": level},
        )
    )
    await db.commit()

    try:
        from worker import process_document_task

        process_document_task.delay(str(doc.id))
    except Exception as e:
        logger.warning("Could not trigger celery task: %s", e)

    return doc


async def _verify_document_in_matter(
    db: AsyncSession,
    user: User,
    matter_id: UUID,
    document_id: UUID,
) -> MatterDocument:
    if not await user_can_access_matter(db, user, matter_id):
        raise HTTPException(status_code=404, detail="Document not found")
    result = await db.execute(
        select(MatterDocument).where(MatterDocument.id == document_id, MatterDocument.matter_id == matter_id)
    )
    doc = result.scalar_one_or_none()
    if not doc:
        raise HTTPException(status_code=404, detail="Document not found")
    await assert_document_accessible(db, user, document_id)
    return doc


@router.get("/{matter_id}/documents/{document_id}/status")
async def get_document_status(
    matter_id: UUID,
    document_id: UUID,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    await _verify_document_in_matter(db, user, matter_id, document_id)
    count_res = await db.execute(
        select(func.count(DocumentChunk.id)).where(DocumentChunk.document_id == document_id)
    )
    if count_res.scalar_one() > 0:
        return {"status": "processed"}
    return {"status": "processing"}


@router.get("/{matter_id}/documents/{document_id}/graph-entities")
async def get_graph_entities(
    matter_id: UUID,
    document_id: UUID,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    await _verify_document_in_matter(db, user, matter_id, document_id)
    nodes = await db.execute(select(GraphNode).where(GraphNode.document_id == document_id))
    entities = [
        {"id": str(n.id), "name": n.name, "type": n.type, "description": n.description}
        for n in nodes.scalars().all()
    ]
    return {"entities": entities}


@router.get("/{matter_id}/documents/{document_id}/graph-edges")
async def get_graph_edges(
    matter_id: UUID,
    document_id: UUID,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    await _verify_document_in_matter(db, user, matter_id, document_id)
    edges_res = await db.execute(
        select(GraphEdge)
        .join(GraphNode, GraphEdge.source_node_id == GraphNode.id)
        .where(GraphNode.document_id == document_id)
    )
    edges = [
        {
            "id": str(e.id),
            "source": str(e.source_node_id),
            "target": str(e.target_node_id),
            "type": e.relationship,
        }
        for e in edges_res.scalars().all()
    ]
    return {"edges": edges}


@router.post("/{matter_id}/analyze", response_model=DocumentAnalysisResponse)
@limiter.limit("20/minute", exempt_when=rate_limit_exempt)
async def analyze_document(
    request: Request,
    matter_id: UUID,
    req: DocumentAnalysisRequest,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    from services.rag import answer_question

    await require_matter_access(matter_id, user, db, min_role="viewer")
    doc = await _verify_document_in_matter(db, user, matter_id, req.document_id)

    try:
        rag_result = await answer_question(
            db,
            req.question,
            use_law_corpus=False,
            document_id=str(req.document_id),
            user=user,
        )
    except HTTPException:
        raise
    except Exception as exc:
        logger.exception("Analyze failed")
        raise HTTPException(status_code=503, detail="Analysis service temporarily unavailable.") from exc

    db.add(
        _audit(
            user,
            "analyze",
            "document",
            str(req.document_id),
            {"question": req.question, "matter_id": str(matter_id)},
        )
    )
    await db.commit()

    return DocumentAnalysisResponse(
        document_id=req.document_id,
        question=req.question,
        answer=rag_result["answer"],
        model=rag_result["model"],
        sources=rag_result["sources"],
    )


@router.post("/{matter_id}/compare", response_model=DocumentCompareResponse)
@limiter.limit("10/minute", exempt_when=rate_limit_exempt)
async def compare_document(
    request: Request,
    matter_id: UUID,
    req: DocumentCompareRequest,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    from services.rag import answer_compare

    await require_matter_access(matter_id, user, db, min_role="viewer")
    doc = await _verify_document_in_matter(db, user, matter_id, req.document_id)

    comparison_question = (
        f"Compare the uploaded document ({doc.filename}) against the GDPR and BGB baseline. "
        "Identify material deviations or non-compliance risks."
    )
    try:
        result = await answer_compare(
            db,
            comparison_question,
            document_id=str(req.document_id),
            user=user,
        )
    except HTTPException:
        raise
    except Exception as exc:
        logger.exception("Compare failed")
        raise HTTPException(status_code=503, detail="Compare service temporarily unavailable.") from exc

    db.add(
        _audit(
            user,
            "compare",
            "document",
            str(req.document_id),
            {"matter_id": str(matter_id)},
        )
    )
    await db.commit()

    return DocumentCompareResponse(
        document_id=req.document_id,
        comparison_result=result["comparison_result"],
        model=result["model"],
    )

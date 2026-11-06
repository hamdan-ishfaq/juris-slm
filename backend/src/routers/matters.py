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

from config import settings
from db import DocumentChunk, GraphEdge, GraphNode, Matter, MatterDeadline, MatterDocument, MatterMember, User, get_db
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
    DocumentCompareClauseRequest,
    DocumentCompareClauseResponse,
    DocumentCompareRequest,
    DocumentCompareResponse,
    DocumentStatusResponse,
    DocumentUploadResponse,
    MatterDeadlineCreate,
    MatterDeadlineResponse,
    MatterDeadlineUpdate,
    MatterCreate,
    MatterResponse,
)
from services.access_control import can_upload_confidentiality
from services.audit_log import log_audit
from services.legal_hold import assert_document_deletable, assert_matter_deletable
from services.upload_security import read_upload_bounded, safe_upload_filename

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/matters", tags=["matters"])

UPLOAD_DIR = Path(__file__).resolve().parent.parent / "data" / "uploads"
VALID_CONFIDENTIALITY = frozenset({"internal", "restricted", "privileged"})
VALID_MEMBER_ROLES = frozenset({"viewer", "editor", "owner"})


@router.post("", response_model=MatterResponse)
async def create_matter(
    req: MatterCreate,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    if not user.org_id:
        raise HTTPException(status_code=400, detail="User must belong to an organization to create matters")
    matter = Matter(
        id=uuid.uuid4(),
        user_id=user.id,
        org_id=user.org_id,
        name=req.name,
        description=req.description,
    )
    db.add(matter)
    db.add(MatterMember(matter_id=matter.id, user_id=user.id, role="owner", invited_by=user.id))
    await log_audit(db, user, "create", "matter", str(matter.id), {"name": req.name})
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
    await assert_matter_deletable(db, matter_id)
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
    await log_audit(db, user, "delete", "matter", str(matter_id))
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
    await log_audit(
        db, user, "invite_member", "matter", str(matter_id), {"user_id": str(target.id), "role": body.role}
    )
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
    await log_audit(db, user, "remove_member", "matter", str(matter_id), {"user_id": str(member_user_id)})
    await db.commit()
    return {"ok": True}


@router.get("/{matter_id}/documents", response_model=list[DocumentUploadResponse])
async def list_documents(
    matter_id: UUID,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    await require_matter_access(matter_id, user, db, min_role="viewer")
    rows = await db.execute(
        select(MatterDocument).where(MatterDocument.matter_id == matter_id).order_by(MatterDocument.uploaded_at.desc())
    )
    return list(rows.scalars().all())


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
    matter = await require_matter_access(matter_id, user, db, min_role="editor")
    if not matter.org_id:
        raise HTTPException(status_code=400, detail="Matter must belong to an organization")
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
        org_id=matter.org_id,
        filename=safe_name,
        file_path=str(file_path),
        confidentiality=level,
    )
    db.add(doc)
    await log_audit(
        db,
        user,
        "upload",
        "document",
        str(doc.id),
        {"filename": safe_name, "matter_id": str(matter_id), "confidentiality": level},
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


@router.get("/{matter_id}/documents/{document_id}/status", response_model=DocumentStatusResponse)
async def get_document_status(
    matter_id: UUID,
    document_id: UUID,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    doc = await _verify_document_in_matter(db, user, matter_id, document_id)
    if doc.ingest_status == "failed":
        return DocumentStatusResponse(status="failed", ocr_used=doc.ocr_used, error=doc.ingest_error)
    if doc.ingest_status == "processed":
        return DocumentStatusResponse(status="processed", ocr_used=doc.ocr_used)
    count_res = await db.execute(
        select(func.count(DocumentChunk.id)).where(DocumentChunk.document_id == document_id)
    )
    if count_res.scalar_one() > 0:
        doc.ingest_status = "processed"
        await db.commit()
        return DocumentStatusResponse(status="processed", ocr_used=doc.ocr_used)
    if doc.ingest_status == "processing":
        return DocumentStatusResponse(status="processing", ocr_used=doc.ocr_used)
    return DocumentStatusResponse(status="processing")


@router.delete("/{matter_id}/documents/{document_id}")
async def delete_document(
    matter_id: UUID,
    document_id: UUID,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    await require_matter_access(matter_id, user, db, min_role="owner")
    doc = await _verify_document_in_matter(db, user, matter_id, document_id)
    await assert_document_deletable(db, document_id, matter_id)
    node_result = await db.execute(select(GraphNode.id).where(GraphNode.document_id == document_id))
    node_ids = node_result.scalars().all()
    if node_ids:
        await db.execute(
            sa_delete(GraphEdge).where(
                (GraphEdge.source_node_id.in_(node_ids)) | (GraphEdge.target_node_id.in_(node_ids))
            )
        )
        await db.execute(sa_delete(GraphNode).where(GraphNode.id.in_(node_ids)))
    await db.execute(sa_delete(DocumentChunk).where(DocumentChunk.document_id == document_id))
    await db.delete(doc)
    await log_audit(db, user, "delete", "document", str(document_id), {"matter_id": str(matter_id)})
    await db.commit()
    return {"ok": True}


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


@router.post("/{matter_id}/documents/{document_id}/graph-extract")
async def reextract_document_graph(
    matter_id: UUID,
    document_id: UUID,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Re-run graph extraction (LLM + heuristic fallback) for a processed document."""
    doc = await _verify_document_in_matter(db, user, matter_id, document_id)
    if doc.ingest_status != "processed":
        raise HTTPException(status_code=400, detail="Document must be processed before graph extraction")

    from services.document_parser import parse_document_ex

    file_path = Path(doc.file_path)
    if not file_path.exists():
        raise HTTPException(status_code=404, detail="Document file not found on disk")

    parsed = parse_document_ex(file_path, doc.filename)
    text = (parsed.text or "").strip()
    if not text:
        raise HTTPException(status_code=400, detail="No text extracted from document")

    from services.graph_persistence import persist_graph_from_text

    counts = await persist_graph_from_text(db, doc, text)
    await log_audit(db, user, "graph_extract", "document", str(document_id), {"matter_id": str(matter_id), **counts})
    await db.commit()
    return {"ok": True, **counts}


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

    doc_text = ""
    try:
        from pathlib import Path
        from services.document_parser import parse_document

        doc_text = parse_document(Path(doc.file_path), doc.filename)
    except Exception:
        pass

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

    from services.clause_risk import score_document_risk
    from services.playbook import run_playbook_checks
    from services.structured_analysis import build_structured_analysis

    doc_type = "nda" if "nda" in doc.filename.lower() else "msa" if "msa" in doc.filename.lower() else "dpa" if "dpa" in doc.filename.lower() else "contract"
    risk = score_document_risk(doc_text, doc_type=doc_type)
    playbook = run_playbook_checks(doc_text, doc_type)
    structured = build_structured_analysis(rag_result["answer"], doc_text, question=req.question)

    await log_audit(
        db,
        user,
        "analyze",
        "document",
        str(req.document_id),
        {"question": req.question, "matter_id": str(matter_id), "risk_level": risk.get("risk_level")},
    )
    await db.commit()

    return DocumentAnalysisResponse(
        document_id=req.document_id,
        question=req.question,
        answer=rag_result["answer"],
        model=rag_result["model"],
        sources=rag_result["sources"],
        structured=structured,
        risk=risk,
        playbook=playbook,
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

    await log_audit(
        db,
        user,
        "compare",
        "document",
        str(req.document_id),
        {"matter_id": str(matter_id)},
    )
    await db.commit()

    return DocumentCompareResponse(
        document_id=req.document_id,
        comparison_result=result["comparison_result"],
        model=result["model"],
    )


@router.post("/{matter_id}/compare-clause", response_model=DocumentCompareClauseResponse)
@limiter.limit("10/minute", exempt_when=rate_limit_exempt)
async def compare_document_clause(
    request: Request,
    matter_id: UUID,
    req: DocumentCompareClauseRequest,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    from db import ClauseLibraryItem
    from services.rag import answer_compare_clause

    await require_matter_access(matter_id, user, db, min_role="viewer")
    doc = await _verify_document_in_matter(db, user, matter_id, req.document_id)
    clause = await db.get(ClauseLibraryItem, req.clause_library_id)
    if not clause or clause.org_id != user.org_id:
        raise HTTPException(status_code=404, detail="Clause library item not found")
    try:
        result = await answer_compare_clause(
            db,
            document_id=str(req.document_id),
            clause=clause,
            user=user,
            question=req.question,
        )
    except HTTPException:
        raise
    except Exception as exc:
        logger.exception("Compare clause failed")
        raise HTTPException(status_code=503, detail="Compare service temporarily unavailable.") from exc

    await log_audit(
        db,
        user,
        "compare_clause",
        "document",
        str(req.document_id),
        {"matter_id": str(matter_id), "clause_id": str(req.clause_library_id)},
    )
    await db.commit()

    return DocumentCompareClauseResponse(
        document_id=req.document_id,
        clause_library_id=req.clause_library_id,
        comparison_result=result["comparison_result"],
        model=result["model"],
        deviation_flag=result["deviation_flag"],
        sources=result.get("sources") or [],
    )


@router.get("/{matter_id}/deadlines", response_model=list[MatterDeadlineResponse])
async def list_matter_deadlines(
    matter_id: UUID,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    await require_matter_access(matter_id, user, db, min_role="viewer")
    rows = await db.execute(
        select(MatterDeadline)
        .where(MatterDeadline.matter_id == matter_id)
        .order_by(MatterDeadline.due_date.asc())
    )
    return [
        MatterDeadlineResponse(
            id=d.id,
            matter_id=d.matter_id,
            title=d.title,
            due_date=d.due_date,
            status=d.status,
            notes=d.notes,
            created_at=d.created_at,
        )
        for d in rows.scalars().all()
    ]


@router.post("/{matter_id}/deadlines", response_model=MatterDeadlineResponse, status_code=201)
async def create_matter_deadline(
    matter_id: UUID,
    body: MatterDeadlineCreate,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    matter = await require_matter_access(matter_id, user, db, min_role="editor")
    if not matter.org_id:
        raise HTTPException(status_code=400, detail="Matter must belong to an organization")
    row = MatterDeadline(
        id=uuid.uuid4(),
        matter_id=matter_id,
        org_id=matter.org_id,
        title=body.title.strip(),
        due_date=body.due_date,
        notes=(body.notes or "").strip() or None,
        status="open",
        created_by=user.id,
    )
    db.add(row)
    await log_audit(db, user, "create", "deadline", str(row.id), {"matter_id": str(matter_id)})
    await db.commit()
    await db.refresh(row)
    return MatterDeadlineResponse(
        id=row.id,
        matter_id=row.matter_id,
        title=row.title,
        due_date=row.due_date,
        status=row.status,
        notes=row.notes,
        created_at=row.created_at,
    )


@router.patch("/{matter_id}/deadlines/{deadline_id}", response_model=MatterDeadlineResponse)
async def update_matter_deadline(
    matter_id: UUID,
    deadline_id: UUID,
    body: MatterDeadlineUpdate,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    await require_matter_access(matter_id, user, db, min_role="editor")
    row = await db.get(MatterDeadline, deadline_id)
    if not row or row.matter_id != matter_id:
        raise HTTPException(status_code=404, detail="Deadline not found")
    if body.title is not None:
        row.title = body.title.strip()
    if body.due_date is not None:
        row.due_date = body.due_date
    if body.status is not None:
        row.status = body.status.strip()
    if body.notes is not None:
        row.notes = body.notes.strip() or None
    await db.commit()
    await db.refresh(row)
    return MatterDeadlineResponse(
        id=row.id,
        matter_id=row.matter_id,
        title=row.title,
        due_date=row.due_date,
        status=row.status,
        notes=row.notes,
        created_at=row.created_at,
    )


@router.delete("/{matter_id}/deadlines/{deadline_id}")
async def delete_matter_deadline(
    matter_id: UUID,
    deadline_id: UUID,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    await require_matter_access(matter_id, user, db, min_role="editor")
    row = await db.get(MatterDeadline, deadline_id)
    if not row or row.matter_id != matter_id:
        raise HTTPException(status_code=404, detail="Deadline not found")
    await db.delete(row)
    await db.commit()
    return {"ok": True}


@router.post("/{matter_id}/documents/bulk")
@limiter.limit("3/hour", exempt_when=rate_limit_exempt)
async def bulk_upload_documents(
    request: Request,
    matter_id: UUID,
    archive: UploadFile = File(...),
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Upload a zip of .txt/.pdf/.docx files into a matter."""
    import io
    import zipfile

    matter = await require_matter_access(matter_id, user, db, min_role="editor")
    if not matter.org_id:
        raise HTTPException(status_code=400, detail="Matter must belong to an organization")
    if not archive.filename or not archive.filename.lower().endswith(".zip"):
        raise HTTPException(status_code=400, detail="Upload must be a .zip archive")

    raw = await archive.read()
    if len(raw) > settings.max_upload_bytes * 5:
        raise HTTPException(status_code=400, detail="Bulk archive too large")

    uploaded: list[str] = []
    doc_ids: list[str] = []
    try:
        with zipfile.ZipFile(io.BytesIO(raw)) as zf:
            for name in zf.namelist():
                if name.endswith("/") or name.startswith("__MACOSX"):
                    continue
                lower = name.lower()
                if not any(lower.endswith(ext) for ext in (".txt", ".pdf", ".docx", ".md", ".eml", ".msg")):
                    continue
                data = zf.read(name)
                safe_name = safe_upload_filename(Path(name).name)
                file_path = UPLOAD_DIR / f"{matter_id}/{safe_name}"
                file_path.parent.mkdir(parents=True, exist_ok=True)
                async with aiofiles.open(file_path, "wb") as fh:
                    await fh.write(data)
                doc = MatterDocument(
                    id=uuid.uuid4(),
                    matter_id=matter_id,
                    org_id=matter.org_id,
                    filename=safe_name,
                    file_path=str(file_path),
                    confidentiality="internal",
                )
                db.add(doc)
                uploaded.append(safe_name)
                doc_ids.append(str(doc.id))
        await db.commit()
    except zipfile.BadZipFile as exc:
        raise HTTPException(status_code=400, detail="Invalid zip file") from exc

    try:
        from worker import process_document_task

        for doc_id in doc_ids:
            process_document_task.delay(doc_id)
    except Exception:
        pass

    return {"uploaded": uploaded, "count": len(uploaded), "document_ids": doc_ids}


@router.post("/{matter_id}/documents/bulk-files")
@limiter.limit("5/hour", exempt_when=rate_limit_exempt)
async def bulk_upload_files(
    request: Request,
    matter_id: UUID,
    files: list[UploadFile] = File(...),
    confidentiality: str = Form(default="internal"),
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Upload multiple documents in one request (folder-style import)."""
    matter = await require_matter_access(matter_id, user, db, min_role="editor")
    if not matter.org_id:
        raise HTTPException(status_code=400, detail="Matter must belong to an organization")
    level = confidentiality.lower().strip()
    if level not in VALID_CONFIDENTIALITY:
        raise HTTPException(status_code=400, detail="Invalid confidentiality level")
    if not can_upload_confidentiality(user.role, level):
        raise HTTPException(status_code=403, detail=f"Cannot upload {level} documents with role {user.role}")
    if not files:
        raise HTTPException(status_code=400, detail="No files provided")
    if len(files) > 50:
        raise HTTPException(status_code=400, detail="Maximum 50 files per bulk upload")

    uploaded: list[str] = []
    doc_ids: list[str] = []
    for file in files:
        safe_name = safe_upload_filename(file.filename)
        payload = await read_upload_bounded(file)
        file_path = UPLOAD_DIR / f"{matter_id}/{safe_name}"
        file_path.parent.mkdir(parents=True, exist_ok=True)
        async with aiofiles.open(file_path, "wb") as fh:
            await fh.write(payload)
        doc = MatterDocument(
            id=uuid.uuid4(),
            matter_id=matter_id,
            org_id=matter.org_id,
            filename=safe_name,
            file_path=str(file_path),
            confidentiality=level,
        )
        db.add(doc)
        uploaded.append(safe_name)
        doc_ids.append(str(doc.id))
    await db.commit()

    try:
        from worker import process_document_task

        for doc_id in doc_ids:
            process_document_task.delay(doc_id)
    except Exception:
        pass

    return {"uploaded": uploaded, "count": len(uploaded), "document_ids": doc_ids}

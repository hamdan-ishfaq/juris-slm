"""Phase 9F — in-browser contract workspace API."""
from __future__ import annotations

import uuid
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import Response
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from contract_schemas import (
    ClauseAnnotationCreate,
    ClauseAnnotationResponse,
    DocumentVersionResponse,
    WorkspaceSaveRequest,
)
from db import ClauseAnnotation, DocumentVersion, MatterDocument, User, get_db
from deps import get_current_user, require_matter_access
from services.audit_log import log_audit
from services.contract_workspace import ensure_initial_version, get_latest_version, save_new_version
from services.export_docx import build_docx_bytes
from services.legal_hold import active_document_hold_exists, assert_document_editable

router = APIRouter(prefix="/api/v1/matters", tags=["contract-workspace"])


def _version_response(v: DocumentVersion, *, read_only: bool) -> DocumentVersionResponse:
    return DocumentVersionResponse(
        id=v.id,
        version_number=v.version_number,
        content_text=v.content_text,
        clauses=v.clauses or [],
        diff_hash=v.diff_hash,
        created_by=v.created_by,
        created_at=v.created_at,
        read_only=read_only,
    )


async def _get_doc(db: AsyncSession, user: User, matter_id: UUID, document_id: UUID) -> MatterDocument:
    await require_matter_access(matter_id, user, db, min_role="viewer")
    result = await db.execute(
        select(MatterDocument).where(MatterDocument.id == document_id, MatterDocument.matter_id == matter_id)
    )
    doc = result.scalar_one_or_none()
    if not doc:
        raise HTTPException(status_code=404, detail="Document not found")
    return doc


@router.get("/{matter_id}/documents/{document_id}/workspace", response_model=DocumentVersionResponse)
async def get_workspace(
    matter_id: UUID,
    document_id: UUID,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    doc = await _get_doc(db, user, matter_id, document_id)
    version = await ensure_initial_version(db, doc, user)
    await db.commit()
    read_only = await active_document_hold_exists(db, document_id=document_id, matter_id=matter_id)
    return _version_response(version, read_only=read_only)


@router.put("/{matter_id}/documents/{document_id}/workspace", response_model=DocumentVersionResponse)
async def save_workspace(
    matter_id: UUID,
    document_id: UUID,
    body: WorkspaceSaveRequest,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    await require_matter_access(matter_id, user, db, min_role="editor")
    doc = await _get_doc(db, user, matter_id, document_id)
    await assert_document_editable(db, document_id, matter_id)
    try:
        version = await save_new_version(
            db,
            doc=doc,
            user=user,
            content_text=body.content_text.strip(),
            expected_version_number=body.expected_version_number,
        )
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc

    await log_audit(
        db,
        user,
        "document_edit",
        "document",
        str(document_id),
        details={"version_id": str(version.id), "version_number": version.version_number, "diff_hash": version.diff_hash},
    )
    await db.commit()
    return _version_response(version, read_only=False)


@router.get("/{matter_id}/documents/{document_id}/versions", response_model=list[DocumentVersionResponse])
async def list_versions(
    matter_id: UUID,
    document_id: UUID,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    doc = await _get_doc(db, user, matter_id, document_id)
    read_only = await active_document_hold_exists(db, document_id=document_id, matter_id=matter_id)
    rows = await db.execute(
        select(DocumentVersion)
        .where(DocumentVersion.document_id == doc.id)
        .order_by(DocumentVersion.version_number.desc())
    )
    return [_version_response(v, read_only=read_only) for v in rows.scalars().all()]


@router.get("/{matter_id}/documents/{document_id}/annotations", response_model=list[ClauseAnnotationResponse])
async def list_annotations(
    matter_id: UUID,
    document_id: UUID,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    await _get_doc(db, user, matter_id, document_id)
    rows = await db.execute(
        select(ClauseAnnotation)
        .where(ClauseAnnotation.document_id == document_id)
        .order_by(ClauseAnnotation.created_at.desc())
    )
    return [
        ClauseAnnotationResponse(
            id=a.id,
            document_id=a.document_id,
            version_id=a.version_id,
            clause_id=a.clause_id,
            comment=a.comment,
            created_by=a.created_by,
            created_at=a.created_at,
        )
        for a in rows.scalars().all()
    ]


@router.post("/{matter_id}/documents/{document_id}/annotations", response_model=ClauseAnnotationResponse)
async def create_annotation(
    matter_id: UUID,
    document_id: UUID,
    body: ClauseAnnotationCreate,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    await require_matter_access(matter_id, user, db, min_role="editor")
    doc = await _get_doc(db, user, matter_id, document_id)
    await assert_document_editable(db, document_id, matter_id)
    version = await get_latest_version(db, doc.id) or await ensure_initial_version(db, doc, user)
    ann = ClauseAnnotation(
        id=uuid.uuid4(),
        document_id=document_id,
        version_id=version.id,
        clause_id=body.clause_id,
        comment=body.comment.strip(),
        created_by=user.id,
    )
    db.add(ann)
    await db.commit()
    await db.refresh(ann)
    return ClauseAnnotationResponse(
        id=ann.id,
        document_id=ann.document_id,
        version_id=ann.version_id,
        clause_id=ann.clause_id,
        comment=ann.comment,
        created_by=ann.created_by,
        created_at=ann.created_at,
    )


@router.get("/{matter_id}/documents/{document_id}/export/docx")
async def export_docx(
    matter_id: UUID,
    document_id: UUID,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    doc = await _get_doc(db, user, matter_id, document_id)
    version = await ensure_initial_version(db, doc, user)
    anns = (
        await db.execute(select(ClauseAnnotation).where(ClauseAnnotation.document_id == document_id))
    ).scalars().all()
    await db.commit()
    data = build_docx_bytes(
        filename=doc.filename,
        content=version.content_text,
        clauses=version.clauses or [],
        annotations=[{"clause_id": a.clause_id, "comment": a.comment} for a in anns],
    )
    safe_name = doc.filename.rsplit(".", 1)[0] + "_export.docx"
    return Response(
        content=data,
        media_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        headers={"Content-Disposition": f'attachment; filename="{safe_name}"'},
    )

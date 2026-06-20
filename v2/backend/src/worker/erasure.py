"""GDPR erasure worker stub — Phase 9B respects legal holds; Phase 9E erasure certificate."""
from __future__ import annotations

import uuid

from sqlalchemy.ext.asyncio import AsyncSession

from db import User
from services.audit_log import log_audit
from services.legal_hold import chunks_under_hold
from services.vector_store import delete_by_document_id


async def erase_document_chunks(
    db: AsyncSession,
    document_id: uuid.UUID,
    *,
    user: User | None = None,
) -> dict:
    """Remove chunks for a document unless an active legal hold applies."""
    if await chunks_under_hold(db, document_id):
        result = {"status": "skipped", "reason": "legal_hold_active", "document_id": str(document_id)}
        if user:
            await log_audit(
                db,
                user,
                "erasure_skipped",
                "document",
                resource_id=str(document_id),
                details=result,
            )
        return result
    deleted = await delete_by_document_id(db, document_id)
    result = {"status": "erased", "document_id": str(document_id), "chunks_deleted": deleted}
    if user:
        await log_audit(
            db,
            user,
            "erasure_certificate",
            "document",
            resource_id=str(document_id),
            details=result,
        )
    await db.commit()
    return result

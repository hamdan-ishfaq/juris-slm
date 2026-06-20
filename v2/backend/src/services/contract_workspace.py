"""Phase 9F — contract workspace persistence."""
from __future__ import annotations

import hashlib
import uuid
from pathlib import Path

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from db import DocumentVersion, MatterDocument, User
from services.contract_clauses import extract_clauses
from services.document_parser import parse_document


def content_diff_hash(prev: str | None, new: str) -> str:
    prev = prev or ""
    return hashlib.sha256(f"{len(prev)}:{prev[-200:]}|{len(new)}:{new[-200:]}".encode()).hexdigest()


async def get_latest_version(db: AsyncSession, document_id: uuid.UUID) -> DocumentVersion | None:
    result = await db.execute(
        select(DocumentVersion)
        .where(DocumentVersion.document_id == document_id)
        .order_by(DocumentVersion.version_number.desc())
        .limit(1)
    )
    return result.scalar_one_or_none()


async def ensure_initial_version(db: AsyncSession, doc: MatterDocument, user: User | None = None) -> DocumentVersion:
    latest = await get_latest_version(db, doc.id)
    if latest:
        return latest
    text = parse_document(Path(doc.file_path), doc.filename)
    clauses = extract_clauses(text)
    version = DocumentVersion(
        id=uuid.uuid4(),
        document_id=doc.id,
        version_number=1,
        content_text=text,
        clauses=clauses,
        diff_hash=content_diff_hash(None, text),
        created_by=user.id if user else None,
    )
    db.add(version)
    await db.flush()
    return version


async def save_new_version(
    db: AsyncSession,
    *,
    doc: MatterDocument,
    user: User,
    content_text: str,
    expected_version_number: int | None,
) -> DocumentVersion:
    latest = await ensure_initial_version(db, doc, user)
    if expected_version_number is not None and latest.version_number != expected_version_number:
        raise ValueError(f"Version conflict: expected v{expected_version_number}, current v{latest.version_number}")

    max_ver = await db.execute(
        select(func.max(DocumentVersion.version_number)).where(DocumentVersion.document_id == doc.id)
    )
    next_num = int(max_ver.scalar_one() or 0) + 1
    clauses = extract_clauses(content_text)
    version = DocumentVersion(
        id=uuid.uuid4(),
        document_id=doc.id,
        version_number=next_num,
        content_text=content_text,
        clauses=clauses,
        diff_hash=content_diff_hash(latest.content_text, content_text),
        created_by=user.id,
    )
    db.add(version)

    # Keep on-disk copy in sync for re-ingest paths
    Path(doc.file_path).write_text(content_text, encoding="utf-8")
    return version

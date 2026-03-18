"""
routers/documents.py - Document Management and Ingestion Endpoints
"""
import os
import re
import shutil
import uuid
import mimetypes
import logging
from typing import Optional
from fastapi import APIRouter, HTTPException, UploadFile, File, Depends, Request, Header, Query, Form
from sqlalchemy.ext.asyncio import AsyncSession
from slowapi import Limiter
from slowapi.util import get_remote_address

from ..db import get_db, User
from ..auth import get_current_user

router = APIRouter(prefix="/documents", tags=["documents"])

limiter = Limiter(key_func=get_remote_address)

ingestion_manager = None
model_manager = None
security_manager = None

logger = logging.getLogger(__name__)

# Valid access levels — enforced server-side regardless of what the frontend sends
VALID_ACCESS_LEVELS = {"level_1", "level_2", "level_3"}


def set_managers(im, mm, sm):
    global ingestion_manager, model_manager, security_manager
    ingestion_manager = im
    model_manager = mm
    security_manager = sm


async def get_authenticated_user(
    authorization: str = Header(None),
    db: AsyncSession = Depends(get_db)
) -> User:
    if not authorization:
        raise HTTPException(
            status_code=401,
            detail="Missing authorization header.",
            headers={"WWW-Authenticate": "Bearer"},
        )
    parts = authorization.split()
    if len(parts) != 2 or parts[0].lower() != "bearer":
        raise HTTPException(
            status_code=401,
            detail="Invalid authorization format. Use: Bearer <token>",
            headers={"WWW-Authenticate": "Bearer"},
        )
    token = parts[1]
    try:
        user = await get_current_user(token, db)
        return user
    except ValueError as e:
        raise HTTPException(
            status_code=401,
            detail=f"Invalid or expired token: {str(e)}",
            headers={"WWW-Authenticate": "Bearer"},
        )


@router.post("/upload")
@limiter.limit("5/hour")
async def upload_document(
    request: Request,
    file: UploadFile = File(...),
    access_level: str = Form(default="level_1"),
    current_user: User = Depends(get_authenticated_user),
    db: AsyncSession = Depends(get_db)
):
    """
    Upload a PDF with an explicit access level.

    access_level values:
      - level_1: accessible to all authenticated users (default)
      - level_2: accessible to admin and owner roles only
      - level_3: accessible to owner only

    Only admin and owner users may upload level_2 or level_3 documents.
    """
    ALLOWED_EXTENSIONS = {'.pdf'}
    MAX_FILE_SIZE = 50 * 1024 * 1024

    # Validate access_level
    if access_level not in VALID_ACCESS_LEVELS:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid access_level '{access_level}'. Must be one of: {sorted(VALID_ACCESS_LEVELS)}"
        )

    # Enforce privilege: only admin/owner can tag documents above level_1
    user_role = str(current_user.role).lower().replace("userrole.", "")
    if access_level in ("level_2", "level_3") and user_role not in ("admin", "owner"):
        raise HTTPException(
            status_code=403,
            detail=f"Only admin or owner users may upload {access_level} documents."
        )

    temp_filename = None
    try:
        file_ext = os.path.splitext(file.filename)[1].lower()
        if file_ext not in ALLOWED_EXTENSIONS:
            raise HTTPException(status_code=400, detail=f"Invalid file type: {file_ext}. Only .pdf files are allowed.")

        mime_type, _ = mimetypes.guess_type(file.filename)
        if mime_type != 'application/pdf':
            raise HTTPException(status_code=400, detail=f"Invalid MIME type: {mime_type}. Expected application/pdf.")

        file.file.seek(0, 2)
        file_size = file.file.tell()
        file.file.seek(0)
        if file_size > MAX_FILE_SIZE:
            raise HTTPException(status_code=413, detail=f"File too large: {file_size / (1024*1024):.1f}MB > 50MB limit")

        safe_filename = re.sub(r'[^a-zA-Z0-9._-]', '_', file.filename)
        temp_filename = f"/tmp/{uuid.uuid4()}_{safe_filename}"

        with open(temp_filename, "wb") as buffer:
            shutil.copyfileobj(file.file, buffer)

        print(f"DEBUG: Uploading file {safe_filename} for user {current_user.email} as {access_level}")
        result = await ingestion_manager.ingest_pdf(
            file_path=temp_filename,
            user_id=current_user.id,
            db=db,
            access_level=access_level
        )

        print(f"DEBUG: Upload successful for user {current_user.email}: {result['doc_id']}")
        return {
            "status": "success",
            "message": f"Successfully ingested {safe_filename}",
            "doc_id": result["doc_id"],
            "access_level": access_level,
            "parent_chunks_created": result["parent_chunks_created"],
            "child_chunks_created": result["child_chunks_created"]
        }

    except HTTPException:
        raise
    except Exception as e:
        print(f"ERROR in upload_document: {type(e).__name__}: {str(e)}")
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=f"Upload failed: {str(e)}")

    finally:
        if temp_filename and os.path.exists(temp_filename):
            try:
                os.remove(temp_filename)
                print(f"DEBUG: Cleaned up temp file {temp_filename}")
            except Exception as cleanup_error:
                print(f"WARNING: Failed to cleanup temp file {temp_filename}: {cleanup_error}")


@router.get("/metadata")
def get_documents_metadata(
    query: Optional[str] = Query(None),
    threshold: float = Query(0.5)
):
    try:
        ingestion_manager._load_db()
        docs = ingestion_manager.documents or []
        metas = ingestion_manager.metadata or []
        out = []
        for i, meta in enumerate(metas):
            snippet = docs[i][:200] if i < len(docs) else ""
            out.append({
                "index": i,
                "doc_id": meta.get("doc_id", f"chunk_{i}"),
                "source": meta.get("source", "Unknown"),
                "role": meta.get("role", "public"),
                "access_level": meta.get("access_level", "level_1"),
                "snippet": snippet
            })
        return {"num_chunks": len(out), "chunks": out}
    except Exception as e:
        logger.error(f"Failed to retrieve document metadata: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to retrieve metadata: {str(e)}")


@router.get("/semantic-search")
def semantic_search(
    query: str = Query(...),
    threshold: float = Query(0.5),
    top_k: int = Query(20)
):
    if not query:
        return {"message": "Provide a 'query' parameter."}
    try:
        model_manager.load_embedding_model()
        ingestion_manager._load_db()
        docs = ingestion_manager.documents or []
        metas = ingestion_manager.metadata or []
        if not docs:
            return {"num_chunks": 0, "results": []}

        from sklearn.metrics.pairwise import cosine_similarity
        q_emb = model_manager.embedding_model.encode([query], convert_to_numpy=True)[0]
        doc_embs = model_manager.embedding_model.encode(docs, convert_to_numpy=True)
        sims = cosine_similarity([q_emb], doc_embs)[0]

        results = []
        for i, score in enumerate(sims):
            if float(score) >= threshold:
                results.append({
                    "index": i,
                    "score": float(score),
                    "role": metas[i].get("role", "public") if i < len(metas) else "public",
                    "access_level": metas[i].get("access_level", "level_1") if i < len(metas) else "level_1",
                    "doc_id": metas[i].get("doc_id", f"chunk_{i}") if i < len(metas) else f"chunk_{i}",
                    "source": metas[i].get("source", "Unknown") if i < len(metas) else "Unknown",
                    "snippet": docs[i][:300]
                })
        results_sorted = sorted(results, key=lambda x: x["score"], reverse=True)[:top_k]
        return {"query": query, "threshold": threshold, "found": len(results_sorted), "results": results_sorted}
    except Exception as e:
        logger.error(f"Semantic search failed: {e}")
        raise HTTPException(status_code=500, detail=f"Semantic search failed: {str(e)}")

"""Upload filename and size validation."""
from __future__ import annotations

import re
from pathlib import Path

from fastapi import HTTPException, UploadFile

from config import settings

_ALLOWED_EXTENSIONS = frozenset({".pdf", ".docx", ".txt", ".md"})


def safe_upload_filename(raw: str | None) -> str:
    """Return basename only; reject path traversal and empty names."""
    if not raw or not str(raw).strip():
        raise HTTPException(status_code=400, detail="Filename is required")
    name = Path(str(raw).replace("\\", "/")).name.strip()
    if not name or name in (".", ".."):
        raise HTTPException(status_code=400, detail="Invalid filename")
    if ".." in name or "\x00" in name:
        raise HTTPException(status_code=400, detail="Invalid filename")
    if not re.match(r"^[\w.\- ()]+$", name):
        raise HTTPException(status_code=400, detail="Filename contains disallowed characters")
    ext = Path(name).suffix.lower()
    if ext not in _ALLOWED_EXTENSIONS:
        raise HTTPException(
            status_code=400,
            detail=f"File type not allowed. Allowed: {', '.join(sorted(_ALLOWED_EXTENSIONS))}",
        )
    return name


async def read_upload_bounded(file: UploadFile, *, max_bytes: int | None = None) -> bytes:
    """Read upload with size cap to prevent memory exhaustion."""
    limit = max_bytes or settings.max_upload_bytes
    chunks: list[bytes] = []
    total = 0
    while True:
        piece = await file.read(1024 * 1024)
        if not piece:
            break
        total += len(piece)
        if total > limit:
            raise HTTPException(
                status_code=413,
                detail=f"File exceeds maximum size of {limit // (1024 * 1024)} MB",
            )
        chunks.append(piece)
    return b"".join(chunks)

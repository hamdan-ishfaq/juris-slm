from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from db import User, get_db
from deps import get_current_user
from schemas import CorpusStatsResponse
from services.vector_store import corpus_stats

router = APIRouter(prefix="/api/v1/corpus", tags=["corpus"])


@router.get("/stats", response_model=CorpusStatsResponse)
async def stats(
    db: AsyncSession = Depends(get_db),
    _user: User = Depends(get_current_user),
):
    data = await corpus_stats(db)
    return CorpusStatsResponse(**data)


@router.post("/dlg/bootstrap")
async def dlg_bootstrap(
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    from services.dlg import ensure_dlg_law_edges

    if user.role not in ("org_admin", "owner"):
        from fastapi import HTTPException

        raise HTTPException(status_code=403, detail="Admin only")
    created = await ensure_dlg_law_edges(db)
    return {"dlg_edges_created": created}


@router.post("/ingest-law")
async def ingest_law_trigger(_user: User = Depends(get_current_user)):
    """Run ingest via CLI: docker compose exec api python /app/src/ingest_law.py"""
    return {
        "message": "Run law ingest with: docker compose exec api python /app/src/ingest_law.py",
        "note": "Heavy CPU job; not run inline to avoid API timeout.",
    }

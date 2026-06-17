from fastapi import APIRouter, Depends, HTTPException, Request, status
import logging
from sqlalchemy.ext.asyncio import AsyncSession

from db import User, get_db
from deps import get_current_user
from rate_limit import limiter, rate_limit_exempt
from schemas import ChatRequest, ChatResponse
from services.rag import answer_question

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/chat", tags=["chat"])


@router.post("", response_model=ChatResponse)
@limiter.limit("10/minute", exempt_when=rate_limit_exempt)
async def chat(
    request: Request,
    body: ChatRequest,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    try:
        result = await answer_question(
            db,
            body.message,
            use_law_corpus=body.use_law_corpus,
            user=user,
            use_hyde=body.use_hyde,
        )
        return ChatResponse(**result)
    except HTTPException:
        raise
    except Exception as exc:
        logger.exception("Chat failed")
        raise HTTPException(
            status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Chat service temporarily unavailable.",
        ) from exc

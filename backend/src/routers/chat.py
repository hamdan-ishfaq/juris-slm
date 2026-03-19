"""
routers/chat.py - Chat and Query Management Endpoints
Handles chat queries, chat history retrieval, and conversation management
"""
import asyncio
import logging
import time
from typing import Optional, Dict, Any
from fastapi import APIRouter, HTTPException, Depends, Request, Header
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession
from slowapi import Limiter
from slowapi.util import get_remote_address
from slowapi.errors import RateLimitExceeded

from ..db import get_db, User, ChatMessage
from ..auth import get_current_user

router = APIRouter(prefix="/chat", tags=["chat"])

# Initialize limiter for chat endpoints
limiter = Limiter(key_func=get_remote_address)

# Global managers - will be set by api.py
query_manager = None
security_manager = None
model_manager = None
gpu_semaphore = None

# Flight Recorder: Store last trace for debugging
LAST_TRACE: Dict[str, Any] = {}


def set_managers(qm, sm, mm, gs):
    """Initialize manager references (called by api.py during startup)"""
    global query_manager, security_manager, model_manager, gpu_semaphore
    query_manager = qm
    security_manager = sm
    model_manager = mm
    gpu_semaphore = gs


class QueryRequest(BaseModel):
    query: str


class QueryResponse(BaseModel):
    answer: str
    sources: list
    status: str


logger = logging.getLogger(__name__)


async def get_authenticated_user(
    authorization: str = Header(None),
    db: AsyncSession = Depends(get_db)
) -> User:
    """Dependency to extract and validate authenticated user from JWT token"""
    print("[DEBUG][auth_dep] get_authenticated_user called")
    if not authorization:
        raise HTTPException(
            status_code=401,
            detail="Missing authorization header. Please provide a valid JWT token.",
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    parts = authorization.split()
    if len(parts) != 2 or parts[0].lower() != "bearer":
        raise HTTPException(
            status_code=401,
            detail="Invalid authorization header format. Use: Bearer <token>",
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    token = parts[1]
    
    try:
        user = await get_current_user(token, db)
        print(f"[DEBUG][auth_dep] User authenticated: {user.email}")
        return user
    except ValueError as e:
        raise HTTPException(
            status_code=401,
            detail=f"Invalid or expired token: {str(e)}",
            headers={"WWW-Authenticate": "Bearer"},
        )



@limiter.limit("10/minute")
@router.post("/query", response_model=QueryResponse)
async def query_engine(
    request: Request,
    query_request: QueryRequest,
    current_user: User = Depends(get_authenticated_user),
    db: AsyncSession = Depends(get_db)
):
    """
    Execute a query against the RAG system with security and rate limiting.
    
    Implements:
    - GPU concurrency control (prevents OOM)
    - User authentication via JWT
    - RBAC (Role-Based Access Control)
    - Chat history persistence
    - Rate limiting (10 queries/minute per IP)
    
    Args:
        request: HTTP request object
        query_request: Query payload with 'query' field
        current_user: Authenticated user from JWT token
        db: Async database session
        
    Returns:
        QueryResponse with answer, sources, and status
        
    Raises:
        HTTPException 400: If query is empty or invalid
        HTTPException 401: If not authenticated
        HTTPException 429: If rate limit exceeded
        HTTPException 500: If backend service not initialized
    """
    global LAST_TRACE
    
    import sys
    print(f"[DEBUG][endpoint] Request received from {current_user.email} - about to acquire GPU semaphore", flush=True)
    sys.stdout.flush()
    
    # GPU Concurrency Control: Acquire semaphore to prevent OOM
    async with gpu_semaphore:
        print(f"[DEBUG][endpoint] GPU semaphore acquired for user {current_user.email}", flush=True)
        sys.stdout.flush()
        try:
            # Input validation
            if not query_request:
                raise HTTPException(status_code=400, detail="Request body cannot be empty")
            
            if not hasattr(query_request, 'query') or query_request.query is None:
                raise HTTPException(status_code=400, detail="Query field is required and cannot be empty")
            
            if not query_request.query.strip():
                raise HTTPException(status_code=400, detail="Query cannot be blank or whitespace only")
            
            # Debug logging with authenticated user info
            print(f"DEBUG: Received request from user: {current_user.email} (role: {current_user.role.value})", flush=True)
            print(f"DEBUG: Query: '{query_request.query}'", flush=True)
            
            # Validate query_manager is initialized
            if query_manager is None:
                print("ERROR: query_manager is None - initialization failed during startup")
                raise HTTPException(status_code=500, detail="Backend query service not initialized. Check server logs.")
            
            # Step A: Save user's message to ChatMessage table
            try:
                user_message = ChatMessage(
                    user_id=current_user.id,
                    role="user",
                    content=query_request.query
                )
                db.add(user_message)
                await db.commit()
                logger.info(f"Saved user message to chat history for user {current_user.id}")
            except Exception as e:
                logger.warning(f"Failed to save user message: {e}")
                await db.rollback()
            
            print(f"DEBUG: Calling query_manager.query(...) with role from JWT: {current_user.role.value}", flush=True)
            t_req = time.time()
            # Step B: Get answer and trace from query manager - USE ROLE FROM JWT TOKEN (TRUSTED)
            answer, trace = await query_manager.query(
                user_query=query_request.query,
                role=current_user.role.value,
                db=db,
                user_id=str(current_user.id)
            )
            
            print(f"DEBUG: Query processed successfully. Answer length: {len(answer) if answer else 0} elapsed={time.time()-t_req:.3f}s", flush=True)
            
            # Step C: Save AI's response asynchronously (optimization)
            async def save_assistant_message():
                try:
                    # Create a new session for async save
                    from ..db import async_session_maker
                    async with async_session_maker() as save_db:
                        assistant_message = ChatMessage(
                            user_id=current_user.id,
                            role="assistant",
                            content=answer
                        )
                        save_db.add(assistant_message)
                        await save_db.commit()
                        logger.info(f"Saved assistant message to chat history for user {current_user.id}")
                except Exception as e:
                    logger.error(f"Failed to save assistant message: {e}")
            
            # Fire and forget - don't block response
            asyncio.create_task(save_assistant_message())
            
            # Store trace in Flight Recorder
            LAST_TRACE.update(trace)
            LAST_TRACE["timestamp"] = time.time()
            
            return {
                "answer": answer,
                "sources": trace.get("retrieved_chunks", []),
                "status": trace.get("status", "success")
            }
        except HTTPException:
            raise
        except Exception as e:
            print(f"ERROR in query_engine: {type(e).__name__}: {str(e)}")
            import traceback
            traceback.print_exc()
            raise HTTPException(status_code=500, detail=str(e))


@router.get("/history")
async def get_chat_history(
    current_user: User = Depends(get_authenticated_user),
    db: AsyncSession = Depends(get_db),
    limit: int = 50
):
    """
    Retrieve chat history for the current user.
    
    Args:
        current_user: Authenticated user from JWT token
        db: Async database session
        limit: Maximum number of messages to return (default: 50)
        
    Returns:
        List of ChatMessage objects for the user, ordered by creation time
        
    Raises:
        HTTPException 401: If not authenticated
        HTTPException 500: If database error occurs
    """
    try:
        from sqlalchemy import select, desc
        
        # Query chat messages for current user
        query = select(ChatMessage).where(
            ChatMessage.user_id == current_user.id
        ).order_by(desc(ChatMessage.timestamp)).limit(limit)
        
        result = await db.execute(query)
        messages = result.scalars().all()
        
        return {
            "user_id": str(current_user.id),
            "message_count": len(messages),
            "messages": [
                {
                    "id": str(msg.id),
                    "role": msg.role,
                    "content": msg.content,
                    "created_at": msg.timestamp.isoformat() if hasattr(msg.timestamp, 'isoformat') else str(msg.timestamp)
                }
                for msg in reversed(messages)  # Reverse to get chronological order
            ]
        }
    except Exception as e:
        logger.error(f"Failed to retrieve chat history: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to retrieve chat history: {str(e)}")


@router.delete("/history")
async def clear_chat_history(
    current_user: User = Depends(get_authenticated_user),
    db: AsyncSession = Depends(get_db)
):
    """
    Clear all chat history for the current user.
    
    Args:
        current_user: Authenticated user from JWT token
        db: Async database session
        
    Returns:
        Success message with number of deleted messages
        
    Raises:
        HTTPException 401: If not authenticated
        HTTPException 500: If database error occurs
    """
    try:
        from sqlalchemy import delete
        
        # Delete all messages for current user
        stmt = delete(ChatMessage).where(ChatMessage.user_id == current_user.id)
        result = await db.execute(stmt)
        await db.commit()
        
        return {
            "status": "success",
            "message": f"Cleared {result.rowcount} messages from chat history"
        }
    except Exception as e:
        logger.error(f"Failed to clear chat history: {e}")
        await db.rollback()
        raise HTTPException(status_code=500, detail=f"Failed to clear chat history: {str(e)}")


@router.get("/trace")
def get_last_trace(current_user: User = Depends(get_authenticated_user)):
    """
    Return the last recorded trace from the Flight Recorder.
    Useful for debugging query processing and security decisions.
    
    Returns:
        Dict with trace information or message if no trace available
    """
    return LAST_TRACE if LAST_TRACE else {"message": "No trace recorded yet. Run a query first."}

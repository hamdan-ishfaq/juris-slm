from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBearer
from auth_utils import decode_token
from db import User, get_db
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
import uuid

security = HTTPBearer()

async def get_current_user(credentials = Depends(security), db: AsyncSession = Depends(get_db)) -> User:
    try:
        payload = decode_token(credentials.credentials)
        user_id = payload.get("sub")
        if not user_id:
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token")
        user_id = uuid.UUID(user_id)
    except ValueError:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token")
    
    result = await db.execute(select(User).where(User.id == user_id))
    user = result.scalar_one_or_none()
    if not user:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="User not found")
    
    return user

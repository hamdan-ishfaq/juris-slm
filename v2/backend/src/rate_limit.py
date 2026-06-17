"""Shared SlowAPI limiter for JurisGuard V2."""
from __future__ import annotations

from fastapi import Request
from slowapi import Limiter
from slowapi.util import get_remote_address

from auth_utils import decode_token
from config import settings


def get_user_or_ip(request: Request) -> str:
    auth = request.headers.get("Authorization", "")
    if auth.lower().startswith("bearer "):
        token = auth[7:].strip()
        try:
            payload = decode_token(token)
            sub = payload.get("sub")
            if sub:
                return f"user:{sub}"
        except ValueError:
            pass
    return get_remote_address(request)


limiter = Limiter(key_func=get_user_or_ip, storage_uri=settings.redis_url)

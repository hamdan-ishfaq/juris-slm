"""Headers that stop browsers sniffing content types, embedding API responses cross-origin, or leaking URLs as referrers."""
from __future__ import annotations

_HEADERS = [
    (b"x-content-type-options", b"nosniff"),
    (b"cross-origin-resource-policy", b"same-origin"),
    (b"referrer-policy", b"no-referrer"),
    (b"x-frame-options", b"DENY"),
]


class SecurityHeadersMiddleware:
    """Plain ASGI, so streamed answers pass through unbuffered."""

    def __init__(self, app):
        self.app = app

    async def __call__(self, scope, receive, send):
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        async def send_with_headers(message):
            if message["type"] == "http.response.start":
                message["headers"] = list(message.get("headers", [])) + _HEADERS
            await send(message)

        await self.app(scope, receive, send_with_headers)

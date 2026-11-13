"""A read-only MCP server over the law corpus: search it, read a provision, check citations (D-018).

Run as its own service (`uvicorn mcp_server:app`). Every request needs `Authorization: Bearer <token>`; the server holds
only the token's SHA-256 (`MCP_TOKEN_SHA256`) and refuses everything when it isn't set. Calls act as `MCP_USER_EMAIL`,
whose organisation decides which uploaded corpora are visible, and each one is written to the audit log. There are no
tools that change data.
"""
from __future__ import annotations

import hashlib
import hmac
import json
import logging

from mcp.server.mcpserver import MCPServer
from mcp.server.transport_security import TransportSecuritySettings
from sqlalchemy import select

from config import settings
from db import User, async_session_factory
from services.audit_log import log_audit, question_hash
from services.law_graph import (
    LAWS,
    cited_in_question,
    existing_provisions,
    linked_provisions,
    provision_chunks,
    provision_label,
)

logger = logging.getLogger(__name__)
_MAX_RESULTS = 10
_MAX_TEXT = 6000

server = MCPServer(
    "jurisguard-law",
    title="JurisGuard law corpus",
    instructions=(
        "Read-only access to GDPR, BDSG, BGB and the EU AI Act as ingested in JurisGuard. search_law finds passages, "
        "get_article returns a provision's text and the provisions it cites or is cited by, and check_citation says "
        "which provisions a text cites and whether each exists."
    ),
)


async def _caller(db) -> User:
    user = (await db.execute(select(User).where(User.email == settings.mcp_user_email))).scalar_one_or_none()
    if user is None:
        raise RuntimeError("MCP_USER_EMAIL doesn't name a user")
    return user


async def _audit(db, user: User, tool: str, details: dict) -> None:
    await log_audit(db, user, "mcp_tool", "law_corpus", details={"tool": tool, **details})
    await db.commit()


@server.tool(description="Search the law corpus. Returns the best passages with their law, provision and title.")
async def search_law(query: str, max_results: int = 5) -> list[dict]:
    from services.rag import _retrieve_and_rank

    async with async_session_factory() as db:
        user = await _caller(db)
        hits = await _retrieve_and_rank(
            db, query, accessible_ids=None, include_law=True, user_role=user.role, doc_uuid=None,
            use_hyde=False, org_id=user.org_id,
        )
        results = [
            {
                "law": (hit.get("metadata") or {}).get("source"),
                "provision": (hit.get("metadata") or {}).get("article"),
                "title": (hit.get("metadata") or {}).get("section_title"),
                "text": hit["content"],
                "chunk_id": str(hit.get("id")),
            }
            for hit in hits[: max(1, min(max_results, _MAX_RESULTS))]
        ]
        await _audit(db, user, "search_law", {"query_hash": question_hash(query), "results": len(results)})
    return results


@server.tool(description=f"The text of one provision, and what it cites and is cited by. law is one of {', '.join(LAWS)}.")
async def get_article(law: str, article: str) -> dict:
    async with async_session_factory() as db:
        user = await _caller(db)
        provision = (law.strip().lower(), article.strip())
        if not await existing_provisions(db, [provision]):
            await _audit(db, user, "get_article", {"provision": f"{provision[0]}:{provision[1]}", "found": False})
            return {"found": False, "law": provision[0], "article": provision[1]}
        chunks = await provision_chunks(db, [provision])
        links = await linked_provisions(db, [provision])
        await _audit(db, user, "get_article", {"provision": f"{provision[0]}:{provision[1]}", "found": True})
    return {
        "found": True,
        "label": provision_label(*provision),
        "title": (chunks[0].get("metadata") or {}).get("section_title") if chunks else "",
        "text": "\n\n".join(chunk["content"] for chunk in chunks)[:_MAX_TEXT],
        "cites": [provision_label(b, c) for _, _, b, c, incoming in links if not incoming],
        "cited_by": [provision_label(b, c) for _, _, b, c, incoming in links if incoming],
    }


@server.tool(description="Which provisions a text cites, and whether each exists in the corpus.")
async def check_citation(text: str) -> list[dict]:
    cited = cited_in_question(text)
    async with async_session_factory() as db:
        user = await _caller(db)
        named = [(law, number) for law, number in cited if law]
        found = set(await existing_provisions(db, named))
        bare = [number for law, number in cited if not law]
        bare_found = await existing_provisions(db, [(law, number) for number in bare for law in LAWS])
        results = [
            {"citation": provision_label(law, number), "law": law, "article": number, "exists": (law, number) in found}
            for law, number in named
        ] + [
            {
                "citation": f"Article {number}",
                "law": None,
                "article": number,
                "exists": any(p[1] == number for p in bare_found),
                "laws_with_it": [provision_label(*p) for p in bare_found if p[1] == number],
            }
            for number in dict.fromkeys(bare)
        ]
        await _audit(db, user, "check_citation", {"text_hash": question_hash(text), "citations": len(results)})
    return results


def _token_ok(header: str) -> bool:
    expected = settings.mcp_token_sha256.strip().lower()
    if not expected or not header.startswith("Bearer "):
        return False
    supplied = hashlib.sha256(header.removeprefix("Bearer ").strip().encode()).hexdigest()
    return hmac.compare_digest(supplied, expected)


def require_token(inner):
    """Refuse any HTTP request without the configured bearer token, before the MCP app sees it."""

    async def app(scope, receive, send):
        if scope["type"] == "http":
            headers = dict(scope.get("headers") or [])
            if not _token_ok(headers.get(b"authorization", b"").decode()):
                body = json.dumps({"error": "missing or invalid bearer token"}).encode()
                await send({"type": "http.response.start", "status": 401, "headers": [
                    (b"content-type", b"application/json"), (b"www-authenticate", b"Bearer")]})
                await send({"type": "http.response.body", "body": body})
                return
        await inner(scope, receive, send)

    return app


def build_app():
    """The HTTP app behind the token check. Each call builds a fresh session manager, which can only run once."""
    return require_token(
        server.streamable_http_app(
            stateless_http=True,
            json_response=True,
            transport_security=TransportSecuritySettings(
                allowed_hosts=[h.strip() for h in settings.mcp_allowed_hosts.split(",") if h.strip()],
            ),
        )
    )


app = build_app()

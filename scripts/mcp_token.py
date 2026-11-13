#!/usr/bin/env python3
"""Make a bearer token for the MCP server (D-018). Give the token to the client; put only its hash in .env."""
import hashlib
import secrets

token = secrets.token_urlsafe(32)
print(f"Token for the client (shown once, not stored):\n  {token}\n")
print(f"Add to .env:\n  MCP_TOKEN_SHA256={hashlib.sha256(token.encode()).hexdigest()}")
print("  MCP_USER_EMAIL=<the user whose organisation the calls act for>")

#!/usr/bin/env python3
"""Connect to the running MCP server with the SDK's own client and call each tool once (D-018).

  MCP_TOKEN=<token> live_check.py [--url http://localhost:8003/mcp] [--output report.json]   (host, after make mcp-up)

It also checks that a missing and a wrong token are refused. The token comes from the environment, never an argument.
"""
from __future__ import annotations

import argparse
import asyncio
import json
import os
import sys
from pathlib import Path

import httpx
from mcp import ClientSession
from mcp.client.streamable_http import create_mcp_http_client, streamable_http_client


async def _call(url: str, token: str) -> dict:
    client = create_mcp_http_client(headers={"Authorization": f"Bearer {token}"})
    async with client, streamable_http_client(url, http_client=client) as streams:
        read, write = streams[0], streams[1]
        async with ClientSession(read, write) as session:
            await session.initialize()
            tools = sorted(t.name for t in (await session.list_tools()).tools)
            out = {"tools": tools}
            for name, args in (
                ("search_law", {"query": "When must a data protection officer be designated?", "max_results": 3}),
                ("get_article", {"law": "gdpr", "article": "37"}),
                ("check_citation", {"text": "Under Article 37 GDPR and § 38 BDSG, and Article 999 GDPR"}),
            ):
                result = await session.call_tool(name, args)
                payload = result.structured_content or json.loads(result.content[0].text)
                out[name] = payload.get("result", payload) if isinstance(payload, dict) else payload
            return out


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--url", default="http://localhost:8003/mcp")
    parser.add_argument("--output")
    args = parser.parse_args()
    token = os.environ["MCP_TOKEN"]
    init = {"jsonrpc": "2.0", "id": 1, "method": "initialize", "params": {
        "protocolVersion": "2025-06-18", "capabilities": {}, "clientInfo": {"name": "check", "version": "1"}}}
    headers = {"Accept": "application/json, text/event-stream", "Content-Type": "application/json"}
    refused = {
        "no_token": httpx.post(args.url, json=init, headers=headers, timeout=10).status_code,
        "wrong_token": httpx.post(args.url, json=init, headers={**headers, "Authorization": "Bearer wrong"}, timeout=10).status_code,
    }
    report = {"refused": refused, **asyncio.run(_call(args.url, token))}
    text = json.dumps(report, indent=1, ensure_ascii=False)
    print(text)
    if args.output:
        Path(args.output).write_text(text + "\n")
    return 0 if refused == {"no_token": 401, "wrong_token": 401} else 1


if __name__ == "__main__":
    sys.exit(main())

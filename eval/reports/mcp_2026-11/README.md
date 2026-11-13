# Read-only MCP server, 2026-11-13

`backend/src/mcp_server.py` (D-018): the official MCP SDK (`mcp` 2.3.0), stateless streamable HTTP on port 8003, started
with `make mcp-up`. Three tools, all read-only:

| Tool | What it does |
|---|---|
| `search_law(query, max_results)` | The product's law search; passages with their law, provision and title |
| `get_article(law, article)` | One provision's text, what it cites and what cites it, from the citation graph (D-016) |
| `check_citation(text)` | Which provisions a text cites and whether each exists |

## Checked against the running server

`eval/mcp/live_check.py` connects with the SDK's own client, as Claude Code does, and calls each tool (`live_check.json`):

- No token: 401. A wrong token: 401.
- Tools listed: exactly `check_citation`, `get_article`, `search_law`.
- `search_law("When must a data protection officer be designated?")` returned GDPR Articles 37, 37 and 39.
- `get_article("gdpr", "37")` returned "Designation of the data protection officer", citing Articles 9, 10 and 39 and cited by
  three provisions.
- `check_citation("Under Article 37 GDPR and § 38 BDSG, and Article 999 GDPR")`: GDPR Art. 37 exists, BDSG § 38 exists, GDPR
  Art. 999 doesn't.
- Each call was written to the hash-chained audit log as `mcp_tool`, with a hash of the query or text rather than the text.

Unit tests (`backend/tests/test_mcp_server.py`) check that a missing token, a wrong token and an unconfigured server are all
refused, and that the only tools offered are these three.

## Security

The server holds only the token's SHA-256 and compares it in constant time; the token itself is shown once by
`scripts/mcp_token.py`. Requests must name an allowed host (`MCP_ALLOWED_HOSTS`), which guards against DNS rebinding.
pip-audit of the image after adding the SDK: 153 packages, no known vulnerabilities (`pip_audit.json`). That audit first
found pip 25.0.1 from the base image, with advisories fixed in 26.2; the images now upgrade pip. Phase 6's audit had not
covered pip itself.

## Connecting Claude Code

```bash
python scripts/mcp_token.py            # put the printed hash and a user's email in .env
make mcp-up
claude mcp add --transport http jurisguard http://localhost:8003/mcp --header "Authorization: Bearer <token>"
```

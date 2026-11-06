from __future__ import annotations

import json
import re
from typing import Any

from services.llm_client import generate_aux

GRAPH_EXTRACTION_PROMPT = """You are a legal AI data extractor.
Analyze the following text chunk and extract key legal entities (nodes) and their relationships (edges).
Entity Types allowed: "Party", "Definition", "Obligation", "Right", "Condition", "Concept".

Output ONLY valid JSON in the following format. Do NOT wrap in markdown or add explanations.
{
  "nodes": [
    {"name": "Entity Name", "type": "Entity Type", "description": "Brief description"}
  ],
  "edges": [
    {"source": "Entity Name 1", "target": "Entity Name 2", "relationship": "e.g., HAS_OBLIGATION, DEFINES"}
  ]
}

Text:
{text}
"""


def _parse_graph_json(raw: str) -> dict[str, Any]:
    cleaned = re.sub(r"```json\s*", "", raw)
    cleaned = re.sub(r"```\s*", "", cleaned).strip()
    try:
        return json.loads(cleaned)
    except json.JSONDecodeError:
        match = re.search(r"\{[\s\S]*\}", cleaned)
        if not match:
            raise
        return json.loads(match.group())


def extract_graph_heuristic(text: str) -> dict[str, Any]:
    """Deterministic fallback when aux LLM is unavailable or returns empty."""
    if not (text or "").strip():
        return {"nodes": [], "edges": []}

    nodes: list[dict[str, str]] = []
    edges: list[dict[str, str]] = []
    seen: dict[str, str] = {}

    def add_node(name: str, ntype: str, description: str = "") -> str | None:
        key = name.strip().lower()
        if not key or key in seen:
            return seen.get(key)
        seen[key] = name.strip()
        nodes.append({"name": name.strip(), "type": ntype, "description": description})
        return name.strip()

    for m in re.finditer(r"^([A-Z][A-Z0-9 \-]{3,60})$", text, re.MULTILINE):
        add_node(m.group(1).strip().title(), "Concept", "Section heading")

    for m in re.finditer(
        r"\b(Receiving Party|Disclosing Party|Confidential Information|Effective Date)\b",
        text,
        re.I,
    ):
        ntype = "Party" if "party" in m.group(1).lower() else "Definition"
        add_node(m.group(1).strip(), ntype)

    for m in re.finditer(r"\b(shall not disclose|shall keep confidential|may terminate|aggregate liability)\b", text, re.I):
        add_node(m.group(1).strip(), "Obligation")

    party = seen.get("receiving party") or seen.get("disclosing party")
    for name in list(seen.values()):
        ntype = next((n["type"] for n in nodes if n["name"] == name), "")
        if party and ntype == "Obligation":
            edges.append({"source": party, "target": name, "relationship": "HAS_OBLIGATION"})
        elif ntype == "Definition" and party:
            edges.append({"source": party, "target": name, "relationship": "DEFINES"})

    if len(nodes) >= 2 and not edges:
        for i in range(len(nodes) - 1):
            edges.append(
                {
                    "source": nodes[i]["name"],
                    "target": nodes[i + 1]["name"],
                    "relationship": "RELATES_TO",
                }
            )

    return {"nodes": nodes[:25], "edges": edges[:40]}


async def extract_graph_from_text(text: str) -> dict[str, Any]:
    prompt_body = GRAPH_EXTRACTION_PROMPT.replace("{text}", text[:4000])
    prompt = f"<|system|>\n{prompt_body}\n<|end|>\n<|assistant|>\n"
    try:
        response = await generate_aux(prompt, task="graph_extract")
        data = _parse_graph_json(response)
        result = {
            "nodes": data.get("nodes", []) if isinstance(data.get("nodes"), list) else [],
            "edges": data.get("edges", []) if isinstance(data.get("edges"), list) else [],
        }
        if result["nodes"] or result["edges"]:
            return result
    except Exception as e:
        print(f"Graph extraction failed: {e}")

    return extract_graph_heuristic(text)

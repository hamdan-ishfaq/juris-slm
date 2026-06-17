from __future__ import annotations

import json
import re
from typing import Any

from services.ollama_client import generate

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


async def extract_graph_from_text(text: str) -> dict[str, Any]:
    prompt_body = GRAPH_EXTRACTION_PROMPT.replace("{text}", text)
    prompt = f"<|system|>\n{prompt_body}\n<|end|>\n<|assistant|>\n"
    try:
        response = await generate(prompt)
        data = _parse_graph_json(response)
        return {
            "nodes": data.get("nodes", []) if isinstance(data.get("nodes"), list) else [],
            "edges": data.get("edges", []) if isinstance(data.get("edges"), list) else [],
        }
    except Exception as e:
        print(f"Graph extraction failed: {e}")
        return {"nodes": [], "edges": []}

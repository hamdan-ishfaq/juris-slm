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

async def extract_graph_from_text(text: str) -> dict[str, Any]:
    prompt = f"<|system|>\n{GRAPH_EXTRACTION_PROMPT.replace('{text}', text)}\n<|end|>\n<|assistant|>\n"
    try:
        response = await generate(prompt)
        # Attempt to parse JSON. Sometimes LLM adds markdown formatting
        response = re.sub(r"```json\s*", "", response)
        response = re.sub(r"```\s*", "", response)
        data = json.loads(response.strip())
        
        nodes = data.get("nodes", [])
        edges = data.get("edges", [])
        return {"nodes": nodes, "edges": edges}
    except Exception as e:
        print(f"Graph extraction failed: {e}")
        return {"nodes": [], "edges": []}

from __future__ import annotations

import httpx

from config import settings

SYSTEM_PROMPT = """You are JurisGuard, an expert legal contract analyst.
Answer using ONLY the provided context. If the context is insufficient, say so clearly.
Cite sources by name (e.g. GDPR Art. 5, BGB section) when possible."""


def build_prompt(context: str, question: str) -> str:
    return f"""<|system|>
{SYSTEM_PROMPT}
<|end|>
<|user|>
Context:
{context}

Question: {question}
<|end|>
<|assistant|>
"""


async def _resolve_model_name(client: httpx.AsyncClient) -> str:
    configured = settings.ollama_model
    try:
        tags = await client.get(f"{settings.ollama_base_url.rstrip('/')}/api/tags")
        if tags.status_code == 200:
            names = [m.get("name", "") for m in tags.json().get("models", [])]
            for name in names:
                base = name.split(":")[0]
                if base == configured or name.startswith(f"{configured}:"):
                    return configured
            if names:
                return names[0].split(":")[0]
    except httpx.HTTPError:
        pass
    return configured


async def generate(prompt: str) -> str:
    base = settings.ollama_base_url.rstrip("/")
    url = f"{base}/api/generate"
    async with httpx.AsyncClient(timeout=180.0) as client:
        model = await _resolve_model_name(client)
        payload = {
            "model": model,
            "prompt": prompt,
            "stream": False,
            "options": {"temperature": 0.1, "num_predict": 1024},
        }
        try:
            r = await client.post(url, json=payload)
            r.raise_for_status()
        except httpx.HTTPError as exc:
            raise RuntimeError(
                f"Ollama request failed ({base}, model={model}): {exc}. "
                "Run: docker compose exec ollama ollama pull phi3.5"
            ) from exc
        data = r.json()
    return (data.get("response") or "").strip()

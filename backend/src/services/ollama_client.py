from __future__ import annotations

import asyncio
import json
import logging

import httpx

from config import settings

logger = logging.getLogger(__name__)


async def check_ollama_reachable() -> tuple[bool, str]:
    base = settings.ollama_base_url.rstrip("/")
    try:
        async with httpx.AsyncClient(timeout=5.0) as client:
            r = await client.get(f"{base}/api/tags")
            if r.status_code != 200:
                return False, f"HTTP {r.status_code}"
            names = [m.get("name", "") for m in r.json().get("models", [])]
            return True, ", ".join(names[:3]) if names else settings.ollama_model
    except httpx.HTTPError as exc:
        return False, str(exc)


def _pick_installed_model(configured: str, installed: list[str]) -> str:
    """Map configured OLLAMA_MODEL to an exact tag Ollama accepts."""
    if not installed:
        return configured
    if configured in installed:
        return configured
    cfg_base = configured.split(":")[0]
    for name in installed:
        if name == configured or name.startswith(f"{configured}:"):
            return name
        if name.split(":")[0] == cfg_base:
            return name
    return installed[0]


def _generation_options() -> dict:
    options = {"temperature": 0.1, "num_predict": 1024, "num_ctx": settings.ollama_num_ctx}
    if settings.ollama_num_gpu is not None:
        options["num_gpu"] = settings.ollama_num_gpu
        # With all layers on the GPU, mapping the file only adds a RAM spike of the model's size at load.
        options["use_mmap"] = False
    return options


async def _generate_with_client(
    client: httpx.AsyncClient,
    *,
    prompt: str,
    model: str,
    max_attempts: int,
) -> str:
    base = settings.ollama_base_url.rstrip("/")
    url = f"{base}/api/generate"
    payload = {
        "model": model,
        "prompt": prompt,
        "stream": False,
        "think": False,
        "options": _generation_options(),
    }
    last_exc: Exception | None = None
    for attempt in range(max_attempts):
        try:
            r = await client.post(url, json=payload)
            r.raise_for_status()
            data = r.json()
            return (data.get("response") or "").strip()
        except httpx.HTTPError as exc:
            last_exc = exc
            if attempt + 1 < max_attempts:
                await asyncio.sleep(3 * (attempt + 1))
                continue
            raise RuntimeError(
                f"Ollama request failed ({base}, model={model}): {exc}. "
                f"Run: ollama pull {model} on the host"
            ) from exc
    raise RuntimeError(f"Ollama request failed ({base}): {last_exc}")


def _chat_payload(
    messages: list[dict[str, str]], *, model: str, stream: bool, json_schema: dict | None = None
) -> dict:
    payload = {
        "model": model,
        "messages": messages,
        "stream": stream,
        "keep_alive": settings.ollama_keep_alive,
        # A thinking model such as Qwen3 otherwise spends the token budget on reasoning and can return an empty answer.
        "think": False,
        "options": _generation_options(),
    }
    if json_schema:
        payload["format"] = json_schema  # Ollama constrains the reply to this schema
    return payload


def _read_chat_reply(data: dict) -> str:
    """Return the reply text, logging when the answer or the prompt was cut short."""
    if data.get("done_reason") == "length":
        logger.warning("Generation stopped at the token cap after %s tokens", data.get("eval_count"))
    if (data.get("prompt_eval_count") or 0) >= settings.ollama_num_ctx:
        logger.warning(
            "Prompt filled the %s-token context window, so its start may have been dropped", settings.ollama_num_ctx
        )
    return ((data.get("message") or {}).get("content") or "").strip()


async def load_model() -> None:
    """Load the generation model with the app's options, so the first question doesn't wait for it."""
    base = settings.ollama_base_url.rstrip("/")
    payload = {"model": settings.ollama_model, "keep_alive": settings.ollama_keep_alive, "options": _generation_options()}
    async with httpx.AsyncClient(timeout=600.0) as client:
        response = await client.post(f"{base}/api/generate", json=payload)
        response.raise_for_status()


async def chat_with_model(
    messages: list[dict[str, str]], *, model: str, max_attempts: int = 3, json_schema: dict | None = None
) -> str:
    base = settings.ollama_base_url.rstrip("/")
    payload = _chat_payload(messages, model=model, stream=False, json_schema=json_schema)
    async with httpx.AsyncClient(timeout=180.0) as client:
        for attempt in range(max_attempts):
            try:
                response = await client.post(f"{base}/api/chat", json=payload)
                response.raise_for_status()
                return _read_chat_reply(response.json())
            except httpx.HTTPError as exc:
                if attempt + 1 == max_attempts:
                    raise RuntimeError(
                        f"Ollama request failed ({base}, model={model}): {exc}. Run: ollama pull {model} on the host"
                    ) from exc
                await asyncio.sleep(3 * (attempt + 1))
    raise RuntimeError("unreachable")


async def chat_with_model_stream(messages: list[dict[str, str]], *, model: str):
    base = settings.ollama_base_url.rstrip("/")
    payload = _chat_payload(messages, model=model, stream=True)
    async with httpx.AsyncClient(timeout=180.0) as client:
        async with client.stream("POST", f"{base}/api/chat", json=payload) as response:
            response.raise_for_status()
            async for line in response.aiter_lines():
                if not line:
                    continue
                data = json.loads(line)
                if data.get("done"):
                    _read_chat_reply({**data, "message": {}})
                    break
                chunk = (data.get("message") or {}).get("content") or ""
                if chunk:
                    yield chunk


async def generate_with_model(prompt: str, *, model: str, max_attempts: int = 3) -> str:
    async with httpx.AsyncClient(timeout=180.0) as client:
        resolved = model
        try:
            tags = await client.get(f"{settings.ollama_base_url.rstrip('/')}/api/tags")
            if tags.status_code == 200:
                names = [m.get("name", "") for m in tags.json().get("models", []) if m.get("name")]
                resolved = _pick_installed_model(model, names)
        except httpx.HTTPError:
            pass
        return await _generate_with_client(client, prompt=prompt, model=resolved, max_attempts=max_attempts)

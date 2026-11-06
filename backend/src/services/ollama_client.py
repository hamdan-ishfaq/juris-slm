from __future__ import annotations

import asyncio

import httpx

from config import settings


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


async def _resolve_model_name(client: httpx.AsyncClient) -> str:
    configured = settings.ollama_model
    try:
        tags = await client.get(f"{settings.ollama_base_url.rstrip('/')}/api/tags")
        if tags.status_code == 200:
            names = [m.get("name", "") for m in tags.json().get("models", []) if m.get("name")]
            return _pick_installed_model(configured, names)
    except httpx.HTTPError:
        pass
    return configured


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


async def generate_with_model_stream(prompt: str, *, model: str):
    base = settings.ollama_base_url.rstrip("/")
    url = f"{base}/api/generate"
    payload = {
        "model": model,
        "prompt": prompt,
        "stream": True,
        "options": _generation_options(),
    }
    async with httpx.AsyncClient(timeout=180.0) as client:
        async with client.stream("POST", url, json=payload) as r:
            r.raise_for_status()
            async for line in r.aiter_lines():
                if not line:
                    continue
                try:
                    data = __import__("json").loads(line)
                    chunk = data.get("response") or ""
                    if chunk:
                        yield chunk
                    if data.get("done"):
                        break
                except Exception:
                    continue


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


async def generate(prompt: str, *, max_attempts: int = 3) -> str:
    async with httpx.AsyncClient(timeout=180.0) as client:
        model = await _resolve_model_name(client)
        return await _generate_with_client(client, prompt=prompt, model=model, max_attempts=max_attempts)

import asyncio
import json
from pathlib import Path

import httpx
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from slowapi import _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded
from slowapi.middleware import SlowAPIMiddleware
from sqlalchemy import text

from config import settings
from db import engine
from rate_limit import limiter
from routers import admin, audit, auth, chat, corpus, matters

app = FastAPI(title=settings.app_name, version="0.4.0")

app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)
app.add_middleware(SlowAPIMiddleware)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://localhost:3000", "http://localhost:8002"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.on_event("startup")
async def startup_event():
    try:
        async with engine.begin() as conn:
            await conn.execute(text("SELECT 1"))
    except Exception as e:
        raise RuntimeError(f"Database connection failed on startup: {e}")

    async def _warm_models() -> None:
        from services.embeddings import get_embedding_model
        from services.reranker import get_reranker

        try:
            await asyncio.to_thread(get_embedding_model)
        except Exception as exc:
            print(f"Embedding preload failed: {exc}")
        try:
            await asyncio.to_thread(get_reranker)
        except Exception as exc:
            print(f"Reranker preload failed: {exc}")

    asyncio.create_task(_warm_models())

app.include_router(auth.router)
app.include_router(corpus.router)
app.include_router(chat.router)
app.include_router(matters.router)
app.include_router(admin.router)
app.include_router(audit.router)


def _read_training_manifest() -> dict | None:
    manifest = settings.training_mount_path / "RUN_MANIFEST.json"
    if not manifest.is_file():
        return None
    try:
        return json.loads(manifest.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return None


@app.get("/health")
async def health():
    return {"status": "ok", "service": settings.app_name, "phase": "phase-1-rbac"}


@app.get("/api/v1/status")
async def status():
    manifest = _read_training_manifest()
    ollama_ok = False
    ollama_models: list[str] = []
    try:
        async with httpx.AsyncClient(timeout=5.0) as client:
            r = await client.get(f"{settings.ollama_base_url.rstrip('/')}/api/tags")
            if r.status_code == 200:
                ollama_ok = True
                ollama_models = [m.get("name", "") for m in r.json().get("models", [])]
    except httpx.HTTPError:
        pass

    from services.celery_status import get_celery_status
    from services.llm_client import active_model_name, check_llm_reachable

    celery_status = await asyncio.to_thread(get_celery_status)
    models_status = _model_assets_status()
    llm_ok, llm_detail = await check_llm_reachable()

    resume_dir = settings.training_mount_path / "checkpoint_RESUME"
    return {
        "llm": {
            "provider": settings.llm_provider,
            "model": active_model_name(),
            "reachable": llm_ok,
            "detail": llm_detail,
        },
        "ollama": {
            "base_url": settings.ollama_base_url,
            "configured_model": settings.ollama_model,
            "reachable": ollama_ok,
            "models": ollama_models,
        },
        "openrouter": {
            "base_url": settings.openrouter_base_url,
            "configured_model": settings.openrouter_model,
            "configured": bool(settings.openrouter_api_key),
        },
        "celery": celery_status,
        "models": models_status,
        "training": {
            "dir": str(settings.training_mount_path),
            "manifest": manifest,
            "resume_checkpoint_exists": (resume_dir / "trainer_state.json").is_file(),
        },
        "database": settings.database_url.split("@")[-1],
        "phase": "phase-1-rbac",
    }


def _model_assets_status() -> dict:
    """Report whether embedding/reranker weights exist on disk (Bug 0.2.1)."""
    def _has_weights(path: Path, min_bytes: int) -> bool:
        if not path.is_dir():
            return False
        for pattern in ("*.safetensors", "pytorch_model.bin"):
            for f in path.glob(pattern):
                if f.is_file() and f.stat().st_size >= min_bytes:
                    return True
        return False

    embed_path = settings.embedding_model_path
    rerank_path = settings.reranker_model_path
    embed_ok = _has_weights(embed_path, 500_000_000)
    rerank_ok = _has_weights(rerank_path, 10_000_000)
    return {
        "embedding_path": str(embed_path),
        "embedding_ready": embed_ok,
        "reranker_path": str(rerank_path),
        "reranker_ready": rerank_ok,
        "ready": embed_ok and rerank_ok,
    }

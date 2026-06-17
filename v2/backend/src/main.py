import asyncio
import json
import logging
from pathlib import Path

import httpx
from fastapi import Depends, FastAPI, HTTPException, status
from fastapi.middleware.cors import CORSMiddleware
from slowapi import _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded
from slowapi.middleware import SlowAPIMiddleware
from sqlalchemy import text

from config import settings
from db import User, engine
from deps import get_current_user
from rate_limit import limiter
from routers import admin, audit, auth, chat, corpus, matters
from services.config_security import is_admin_role, validate_settings

logger = logging.getLogger(__name__)

_openapi_url = "/openapi.json" if settings.expose_openapi else None
_docs_url = "/docs" if settings.expose_openapi else None
_redoc_url = "/redoc" if settings.expose_openapi else None

app = FastAPI(
    title=settings.app_name,
    version="0.5.0",
    docs_url=_docs_url,
    redoc_url=_redoc_url,
    openapi_url=_openapi_url,
)

app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)
app.add_middleware(SlowAPIMiddleware)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "DELETE", "OPTIONS"],
    allow_headers=["Authorization", "Content-Type"],
)


@app.on_event("startup")
async def startup_event():
    validate_settings()

    try:
        async with engine.begin() as conn:
            await conn.execute(text("SELECT 1"))
    except Exception as e:
        raise RuntimeError(f"Database connection failed on startup: {e}") from e

    from services.dev_master import ensure_dev_master_user

    await ensure_dev_master_user()

    async def _warm_models() -> None:
        from services.embeddings import get_embedding_model
        from services.reranker import get_reranker

        try:
            await asyncio.to_thread(get_embedding_model)
        except Exception as exc:
            logger.warning("Embedding preload failed: %s", exc)
        try:
            await asyncio.to_thread(get_reranker)
        except Exception as exc:
            logger.warning("Reranker preload failed: %s", exc)

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
    return {
        "status": "ok",
        "service": settings.app_name,
        "phase": "phase-3-eval",
        "environment": settings.environment,
    }


def _public_status_subset(*, llm_ok: bool, llm_detail: str, models_status: dict) -> dict:
    from services.build_info import compute_build_hash
    from services.llm_client import active_model_name

    return {
        "phase": "phase-3-eval",
        "environment": settings.environment,
        "build_hash": compute_build_hash(),
        "llm": {
            "provider": settings.llm_provider,
            "model": active_model_name(),
            "reachable": llm_ok,
        },
        "models": {
            "embedding_ready": models_status.get("embedding_ready"),
            "reranker_ready": models_status.get("reranker_ready"),
            "ready": models_status.get("ready"),
        },
        "retrieval": {
            "hybrid_search": settings.hybrid_search_enabled,
            "hyde_default": settings.hyde_enabled,
            "contextual_retrieval": settings.contextual_retrieval_enabled,
            "citation_verify": settings.citation_verify_enabled,
        },
        "eval": {
            "golden_cases": 95,
            "baseline": "eval/baseline.json",
        },
    }


@app.get("/api/v1/status")
async def status(user: User = Depends(get_current_user)):
    """Authenticated status — admin roles receive extended operational detail."""
    from services.build_info import compute_build_hash
    from services.celery_status import get_celery_status
    from services.llm_client import active_model_name, check_llm_reachable

    celery_status = await asyncio.to_thread(get_celery_status)
    models_status = _model_assets_status()
    llm_ok, llm_detail = await check_llm_reachable()

    base = _public_status_subset(llm_ok=llm_ok, llm_detail=llm_detail, models_status=models_status)

    if not is_admin_role(user.role):
        return base

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

    manifest = _read_training_manifest()
    resume_dir = settings.training_mount_path / "checkpoint_RESUME"
    return {
        **base,
        "llm": {
            **base["llm"],
            "detail": llm_detail,
        },
        "ollama": {
            "reachable": ollama_ok,
            "configured_model": settings.ollama_model,
            "model_count": len(ollama_models),
        },
        "openrouter": {
            "configured_model": settings.openrouter_model,
            "configured": bool(settings.openrouter_api_key),
        },
        "celery": {
            "reachable": celery_status.get("reachable"),
            "workers": len(celery_status.get("workers") or []),
            "active_tasks": celery_status.get("active_tasks"),
        },
        "database": {"connected": True},
        "training": {
            "manifest_present": manifest is not None,
            "resume_checkpoint_exists": (resume_dir / "trainer_state.json").is_file(),
        },
        "dev_master": {"enabled": settings.dev_master_enabled},
        "build_hash": compute_build_hash(),
    }


def _model_assets_status() -> dict:
    """Report whether embedding/reranker weights exist on disk."""

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
        "embedding_ready": embed_ok,
        "reranker_ready": rerank_ok,
        "ready": embed_ok and rerank_ok,
    }

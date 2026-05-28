import json
from pathlib import Path

import httpx
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import text

from config import settings
from db import engine
from routers import auth, chat, corpus, matters

app = FastAPI(title=settings.app_name, version="0.3.0")

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

app.include_router(auth.router)
app.include_router(corpus.router)
app.include_router(chat.router)
app.include_router(matters.router)


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
    return {"status": "ok", "service": settings.app_name, "phase": "2.2-3"}


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

    resume_dir = settings.training_mount_path / "checkpoint_RESUME"
    return {
        "ollama": {
            "base_url": settings.ollama_base_url,
            "configured_model": settings.ollama_model,
            "reachable": ollama_ok,
            "models": ollama_models,
        },
        "training": {
            "dir": str(settings.training_mount_path),
            "manifest": manifest,
            "resume_checkpoint_exists": (resume_dir / "trainer_state.json").is_file(),
        },
        "database": settings.database_url.split("@")[-1],
        "phase": "2.2-auth, 2.3-corpus, 3-rag",
    }

# api.py
# src/api.py - FastAPI application factory and initialization
print("API module loaded")
import asyncio
import logging
import time
import os
from pathlib import Path
from typing import Optional, Dict, Any
from contextlib import asynccontextmanager
from fastapi import FastAPI, HTTPException, Depends, Security
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.util import get_remote_address
from slowapi.errors import RateLimitExceeded

from .models import ModelManager
from .security import SecurityManager
from .ingestion import IngestionManager
from .query import QueryManager
from .eval import run_evaluation_suite
from .db import init_db, close_db
from .auth import set_auth_config
import src.auth as _auth_module
from .routers import auth as auth_router
from .routers import admin as admin_router
from .routers import chat as chat_router
from .routers import documents as documents_router
from config import config

logger = logging.getLogger(__name__)

model_manager: Optional[ModelManager] = None
security_manager: Optional[SecurityManager] = None
ingestion_manager: Optional[IngestionManager] = None
query_manager: Optional[QueryManager] = None

gpu_semaphore = asyncio.Semaphore(1)
limiter = Limiter(key_func=get_remote_address)
LAST_EVALUATION: Dict[str, Any] = {}

_bearer_scheme = HTTPBearer(auto_error=True)


def require_valid_token(
    credentials: HTTPAuthorizationCredentials = Security(_bearer_scheme)
) -> str:
    """
    Lightweight JWT verifier. Reads SECRET_KEY lazily at call time,
    not at import time — avoids None capture before lifespan sets it.
    """
    from jose import JWTError, jwt as jose_jwt
    token = credentials.credentials
    secret = _auth_module.SECRET_KEY
    algorithm = _auth_module.ALGORITHM
    if not secret:
        raise HTTPException(status_code=503, detail="Auth not yet initialised")
    try:
        jose_jwt.decode(token, secret, algorithms=[algorithm])
        return token
    except JWTError:
        raise HTTPException(status_code=401, detail="Invalid or expired token")
def require_owner(
    credentials: HTTPAuthorizationCredentials = Security(_bearer_scheme)
) -> str:
    from jose import JWTError, jwt as jose_jwt
    token = credentials.credentials
    secret = _auth_module.SECRET_KEY
    algorithm = _auth_module.ALGORITHM
    if not secret:
        raise HTTPException(status_code=503, detail="Auth not yet initialised")
    try:
        payload = jose_jwt.decode(token, secret, algorithms=[algorithm])
        role = (payload.get("role") or "").lower()
        if role != "owner":
            raise HTTPException(status_code=403, detail="Owner access required")
        return token
    except JWTError:
        raise HTTPException(status_code=401, detail="Invalid or expired token")


def _resolve_origins() -> list:
    env_raw = os.environ.get("ALLOWED_ORIGINS", "")
    env_origins = [o.strip() for o in env_raw.split(",") if o.strip()]
    config_origins = [o for o in getattr(config.api, "origins", []) if o != "*"]
    merged = list(dict.fromkeys(env_origins + config_origins))
    if not merged:
        merged = ["http://localhost:5173", "http://localhost:8001"]
        logger.warning("No ALLOWED_ORIGINS configured — falling back to localhost only.")
    logger.info(f"CORS allowed origins: {merged}")
    return merged


def _is_production() -> bool:
    return os.environ.get("ENVIRONMENT", "development").lower() == "production"


@asynccontextmanager
async def lifespan(app: FastAPI):
    global model_manager, security_manager, ingestion_manager, query_manager
    print("🚀 Starting JurisGuardRAG Engine...")

    try:
        await init_db(config.auth.database_url)
        print("✅ Database initialized")
    except Exception as e:
        print(f"⚠️  Failed to initialize database: {e}")

    try:
        set_auth_config(
            secret_key=config.auth.secret_key,
            algorithm=config.auth.algorithm,
            expire_minutes=config.auth.access_token_expire_minutes
        )
        print("✅ Authentication configured")
    except Exception as e:
        print(f"⚠️  Failed to configure auth: {e}")

    try:
        model_manager = ModelManager(config)
        print("✅ ModelManager initialized")
    except Exception as e:
        print(f"Failed to initialize ModelManager: {e}")
        model_manager = None

    try:
        security_manager = SecurityManager(config)
        print("✅ SecurityManager initialized")
    except Exception as e:
        print(f"Failed to initialize SecurityManager: {e}")
        security_manager = None

    try:
        ingestion_manager = IngestionManager(config, model_manager, security_manager)
        print("✅ IngestionManager initialized")
    except Exception as e:
        print(f"Failed to initialize IngestionManager: {e}")
        ingestion_manager = None

    try:
        query_manager = QueryManager(config, model_manager, security_manager, ingestion_manager)
        print("✅ QueryManager initialized")
    except Exception as e:
        print(f"Failed to initialize QueryManager: {e}")
        query_manager = None

    try:
        chat_router.set_managers(query_manager, security_manager, model_manager, gpu_semaphore)
        print("✅ Chat router initialized with managers")
    except Exception as e:
        print(f"⚠️  Failed to initialize chat router: {e}")

    try:
        documents_router.set_managers(ingestion_manager, model_manager, security_manager)
        print("✅ Documents router initialized with managers")
    except Exception as e:
        print(f"⚠️  Failed to initialize documents router: {e}")

    print("🔄 Pre-loading models in background...")
    import threading
    def load_models_bg():
        try:
            print("[MODEL_PRELOAD] Loading embedding model...")
            model_manager.load_embedding_model()
            print("[MODEL_PRELOAD] ✅ Embedding model loaded")
            print("[MODEL_PRELOAD] Loading LLM (this may take 2-3 minutes)...")
            model_manager.load_llm()
            print("[MODEL_PRELOAD] ✅ LLM loaded - backend ready for queries!")
        except Exception as e:
            print(f"[MODEL_PRELOAD] ❌ Error loading models: {e}")
            import traceback
            traceback.print_exc()

    loader_thread = threading.Thread(target=load_models_bg, daemon=True)
    loader_thread.start()
    print("✅ Model pre-loading started in background")

    yield

    print("🛑 Shutting down Engine...")
    if model_manager:
        model_manager.unload_models()
    try:
        await close_db()
        print("✅ Database closed")
    except Exception as e:
        print(f"⚠️  Error closing database: {e}")


def create_app() -> FastAPI:
    app = FastAPI(title="Juris Guard API", lifespan=lifespan)

    app.state.limiter = limiter
    app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

    app.add_middleware(
        CORSMiddleware,
        allow_origins=_resolve_origins(),
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    app.include_router(auth_router.router)
    app.include_router(admin_router.router)
    app.include_router(chat_router.router)
    app.include_router(documents_router.router)

    @app.get("/health")
    def health_check():
        llm_loaded = (
            model_manager is not None
            and model_manager.llm_model is not None
        )
        return {
            "status": "active",
            "timestamp": time.time(),
            "models_loaded": llm_loaded,
            "cache": "redis_configured",
            "rate_limiting": "enabled"
        }

    @app.get("/debug/metadata")
    def debug_metadata(token: str = Depends(require_owner)):
        if _is_production():
            raise HTTPException(status_code=404, detail="Not found")
        ingestion_manager._load_db()
        docs = ingestion_manager.documents or []
        metas = ingestion_manager.metadata or []
        out = []
        for i, meta in enumerate(metas):
            snippet = docs[i][:200] if i < len(docs) else ""
            out.append({
                "index": i,
                "doc_id": meta.get("doc_id", f"chunk_{i}"),
                "source": meta.get("source", "Unknown"),
                "role": meta.get("role", "public"),
                "access_level": meta.get("access_level", "level_1"),
                "snippet": snippet
            })
        return {"num_chunks": len(out), "chunks": out}

    @app.get("/debug/semantic")
    def debug_semantic(
        query: Optional[str] = None,
        threshold: float = config.security.similarity_threshold,
        top_k: int = 20,
        token: str = Depends(require_owner)
    ):
        if _is_production():
            raise HTTPException(status_code=404, detail="Not found")
        if query is None:
            return {"message": "Provide a 'query' parameter."}
        from sklearn.metrics.pairwise import cosine_similarity
        model_manager.load_embedding_model()
        ingestion_manager._load_db()
        docs = ingestion_manager.documents or []
        metas = ingestion_manager.metadata or []
        if not docs:
            return {"num_chunks": 0, "results": []}
        q_emb = model_manager.embedding_model.encode([query], convert_to_numpy=True)[0]
        doc_embs = model_manager.embedding_model.encode(docs, convert_to_numpy=True)
        sims = cosine_similarity([q_emb], doc_embs)[0]
        results = []
        for i, score in enumerate(sims):
            if float(score) >= threshold:
                results.append({
                    "index": i,
                    "score": float(score),
                    "role": metas[i].get("role", "public") if i < len(metas) else "public",
                    "access_level": metas[i].get("access_level", "level_1") if i < len(metas) else "level_1",
                    "doc_id": metas[i].get("doc_id", f"chunk_{i}") if i < len(metas) else f"chunk_{i}",
                    "source": metas[i].get("source", "Unknown") if i < len(metas) else "Unknown",
                    "snippet": docs[i][:300]
                })
        results_sorted = sorted(results, key=lambda x: x["score"], reverse=True)[:top_k]
        return {"query": query, "threshold": threshold, "found": len(results_sorted), "results": results_sorted}

    @app.get("/debug/trace")
    def debug_trace(
        query: Optional[str] = None,
        role: str = "guest",
        threshold: float = config.security.similarity_threshold,
        token: str = Depends(require_owner)
    ):
        if _is_production():
            raise HTTPException(status_code=404, detail="Not found")
        if query is None:
            return {"message": "Provide a 'query' parameter."}
        from sklearn.metrics.pairwise import cosine_similarity
        trace = {}
        hf = security_manager.check_query(query)
        trace["layer1"] = hf
        if hf["hard_filter"].get("forced_role") == "admin" and role.lower() != "admin":
            trace["decision"] = {"blocked": True, "reason": "layer1_hard_filter"}
            return trace
        model_manager.load_embedding_model()
        ingestion_manager._load_db()
        docs = ingestion_manager.documents or []
        metas = ingestion_manager.metadata or []
        q_emb = model_manager.embedding_model.encode([query], convert_to_numpy=True)[0]
        doc_embs = model_manager.embedding_model.encode(docs, convert_to_numpy=True)
        sims = cosine_similarity([q_emb], doc_embs)[0]
        cand = sorted(
            [{"index": i, "score": float(sims[i]), "role": metas[i].get("role", "public"), "access_level": metas[i].get("access_level", "level_1")} for i in range(len(docs))],
            key=lambda x: x["score"], reverse=True
        )[:50]
        cand_filtered = [c for c in cand if c["score"] >= threshold]
        trace["layer2_candidates"] = cand_filtered
        sent = security_manager.check_query(query)["sentinel"]
        trace["sentinel_query"] = sent
        if sent.get("label") in ["sensitive"] and sent.get("score", 0) > 0.5 and role.lower() != "admin":
            trace["decision"] = {"blocked": True, "reason": "sentinel_detected_sensitive"}
            return trace
        allowed_idx = [c["index"] for c in cand_filtered if c["role"] == "public"]
        trace["layer3_allowed_indices"] = allowed_idx
        trace["decision"] = {
            "blocked": len(allowed_idx) == 0,
            "reason": "no_public_chunks" if len(allowed_idx) == 0 else "allowed"
        }
        return trace

    @app.get("/debug/last")
    def get_last_trace(token: str = Depends(require_owner)):
        if _is_production():
            raise HTTPException(status_code=404, detail="Not found")
        return chat_router.LAST_TRACE if chat_router.LAST_TRACE else {"message": "No trace recorded yet."}

    @app.post("/evaluate")
    async def run_eval(token: str = Depends(require_owner)):
        global LAST_EVALUATION
        # If already running, return current status
        if LAST_EVALUATION.get("status") == "running":
            return LAST_EVALUATION
        print("⚡ RECEIVED EVALUATION REQUEST - STARTING IN BACKGROUND...", flush=True)
        LAST_EVALUATION = {"status": "running", "test_count": 0, "passed": 0, "failed": 0, "results": []}

        import asyncio, threading
        def run_in_thread():
            global LAST_EVALUATION
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            try:
                results = loop.run_until_complete(
                    run_evaluation_suite(query_manager, ingestion_manager, security_manager)
                )
                LAST_EVALUATION = {
                    "status": "completed",
                    "test_count": len(results),
                    "passed": sum(1 for r in results if r.get("status") == "PASS"),
                    "failed": sum(1 for r in results if r.get("status") == "FAIL"),
                    "results": results
                }
                print("⚡ EVALUATION COMPLETE", flush=True)
            except Exception as e:
                LAST_EVALUATION = {"status": "error", "detail": str(e), "results": []}
            finally:
                loop.close()

        threading.Thread(target=run_in_thread, daemon=True).start()
        return LAST_EVALUATION

    @app.get("/debug/evaluation")
    def get_last_evaluation(token: str = Depends(require_owner)):
        if _is_production():
            raise HTTPException(status_code=404, detail="Not found")
        if not LAST_EVALUATION:
            return {"message": "No evaluation run yet. POST /evaluate first."}
        enhanced_results = []
        for test_result in LAST_EVALUATION.get("results", []):
            enhanced = dict(test_result)
            if "retrieved_chunks" not in enhanced:
                enhanced["retrieved_chunks"] = []
            if "security_blocked" not in enhanced:
                enhanced["security_blocked"] = []
            enhanced_results.append(enhanced)
        return {
            "status": LAST_EVALUATION.get("status"),
            "test_count": LAST_EVALUATION.get("test_count"),
            "passed": LAST_EVALUATION.get("passed"),
            "failed": LAST_EVALUATION.get("failed"),
            "results": enhanced_results
        }

    frontend_dist_path = Path(__file__).parent.parent.parent / "frontend" / "dist"
    if frontend_dist_path.exists():
        app.mount("/assets", StaticFiles(directory=frontend_dist_path / "assets", html=False), name="assets")

        @app.get("/{rest_of_path:path}")
        async def serve_spa(rest_of_path: str = ""):
            if rest_of_path and rest_of_path.startswith(
                ("api/", "auth/", "chat/", "documents/", "admin/", "debug/", "health", "evaluate")
            ):
                raise HTTPException(status_code=404, detail="Not found")
            index_html = frontend_dist_path / "index.html"
            if index_html.exists():
                return FileResponse(index_html)
            raise HTTPException(status_code=500, detail="Frontend not built.")

        print(f"✅ Frontend served from {frontend_dist_path}")
    else:
        print(f"⚠️  Frontend dist not found at {frontend_dist_path}")

    return app

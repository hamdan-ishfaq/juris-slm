# api.py
# src/api.py - FastAPI endpoints
print("API module loaded")
import os
import shutil
import time
from fastapi import FastAPI, HTTPException, UploadFile, File, Query
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import Optional
from contextlib import asynccontextmanager
from sklearn.metrics.pairwise import cosine_similarity

from .models import ModelManager
from .security import SecurityManager
from .ingestion import IngestionManager
from .query import QueryManager
from .eval import run_evaluation_suite
from config import config

# Global managers
model_manager = None
security_manager = None
ingestion_manager = None
query_manager = None

# Flight Recorder: Store last trace for debugging
LAST_TRACE = {}
LAST_EVALUATION = {}

class QueryRequest(BaseModel):
    query: str
    role: str

class QueryResponse(BaseModel):
    answer: str
    sources: list
    status: str

@asynccontextmanager
async def lifespan(app: FastAPI):
    global model_manager, security_manager, ingestion_manager, query_manager
    print("🚀 Starting JurisGuardRAG Engine...")
    try:
        model_manager = ModelManager(config)
        print("ModelManager initialized")
    except Exception as e:
        print(f"Failed to initialize ModelManager: {e}")
        model_manager = None
    
    try:
        security_manager = SecurityManager(config)
        print("SecurityManager initialized")
    except Exception as e:
        print(f"Failed to initialize SecurityManager: {e}")
        security_manager = None
    
    try:
        ingestion_manager = IngestionManager(config, model_manager, security_manager)
        print("IngestionManager initialized")
    except Exception as e:
        print(f"Failed to initialize IngestionManager: {e}")
        ingestion_manager = None
    
    try:
        query_manager = QueryManager(config, model_manager, security_manager, ingestion_manager)
        print("QueryManager initialized")
    except Exception as e:
        print(f"Failed to initialize QueryManager: {e}")
        query_manager = None
    
    yield
    print("🛑 Shutting down Engine...")
    if model_manager:
        model_manager.unload_models()

def create_app() -> FastAPI:
    app = FastAPI(title="Juris Guard API", lifespan=lifespan)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=config.api.origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    @app.get("/")
    def root():
        return {"message": "JurisGuardRAG API", "status": "running"}

    @app.get("/debug/metadata")
    def debug_metadata():
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
                "snippet": snippet
            })
        return {"num_chunks": len(out), "chunks": out}

    @app.get("/debug/semantic")
    def debug_semantic(query: Optional[str] = None, threshold: float = config.security.similarity_threshold, top_k: int = 20):
        if query is None:
            return {"message": "Please provide a 'query' parameter to test semantic search.", "example": "/debug/semantic?query=notice%20period"}
        
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
                    "doc_id": metas[i].get("doc_id", f"chunk_{i}") if i < len(metas) else f"chunk_{i}",
                    "source": metas[i].get("source", "Unknown") if i < len(metas) else "Unknown",
                    "snippet": docs[i][:300]
                })
        results_sorted = sorted(results, key=lambda x: x["score"], reverse=True)[:top_k]
        return {"query": query, "threshold": threshold, "found": len(results_sorted), "results": results_sorted}

    def query_with_rbac(query_text: str, role: str, threshold: float = config.security.similarity_threshold):
        # Simplified RBAC wrapper
        if role.lower() == "admin":
            return query_manager.query(query_text, role)

        # For guest: semantic filter
        model_manager.load_embedding_model()
        ingestion_manager._load_db()
        docs = ingestion_manager.documents or []
        if not docs:
            return {"answer": "No data.", "sources": [], "status": "empty"}

        q_emb = model_manager.embedding_model.encode([query_text], convert_to_numpy=True)[0]
        doc_embs = model_manager.embedding_model.encode(docs, convert_to_numpy=True)
        sims = cosine_similarity([q_emb], doc_embs)[0]

        candidate_idx = [i for i, s in enumerate(sims) if float(s) >= threshold]
        allowed_idx = [i for i in candidate_idx if ingestion_manager.metadata[i].get("role", "public") == "public"]

        if not allowed_idx:
            return {"answer": "Access denied.", "sources": [], "status": "blocked"}

        return query_manager.query(query_text, role, allowed_indices=allowed_idx)

    @app.get("/debug/trace")
    def debug_trace(query: Optional[str] = None, role: str = "guest", threshold: float = config.security.similarity_threshold):
        if query is None:
            return {"message": "Please provide a 'query' parameter to trace security checks.", "example": "/debug/trace?query=salary&role=guest"}
        
        trace = {}
        hf = security_manager.check_query(query)
        trace["layer1"] = hf

        if hf["hard_filter"].get("forced_role") == "admin" and role.lower() != "admin":
            trace["decision"] = {"blocked": True, "reason": "layer1_hard_filter"}
            return trace

        # Layer 2
        model_manager.load_embedding_model()
        ingestion_manager._load_db()
        docs = ingestion_manager.documents or []
        metas = ingestion_manager.metadata or []
        q_emb = model_manager.embedding_model.encode([query], convert_to_numpy=True)[0]
        doc_embs = model_manager.embedding_model.encode(docs, convert_to_numpy=True)
        sims = cosine_similarity([q_emb], doc_embs)[0]

        cand = sorted([{"index": i, "score": float(sims[i]), "role": metas[i].get("role","public")} for i in range(len(docs))], key=lambda x: x["score"], reverse=True)[:50]
        cand_filtered = [c for c in cand if c["score"] >= threshold]
        trace["layer2_candidates_above_threshold"] = cand_filtered

        sent = security_manager.check_query(query)["sentinel"]
        trace["sentinel_query"] = sent
        if sent.get("label") in ["sensitive"] and sent.get("score", 0) > 0.5 and role.lower() != "admin":
            trace["decision"] = {"blocked": True, "reason": "sentinel_detected_sensitive"}
            return trace

        allowed_idx = [c["index"] for c in cand_filtered if c["role"] == "public"]
        trace["layer3_allowed_indices"] = allowed_idx
        trace["decision"] = {"blocked": len(allowed_idx) == 0, "reason": "no_public_chunks" if len(allowed_idx) == 0 else "allowed"}
        return trace

    @app.get("/health")
    def health_check():
        gpu_status = model_manager.get_gpu_status() if model_manager else "N/A"
        return {"status": "active", "gpu_memory_used": gpu_status}

    @app.post("/query", response_model=QueryResponse)
    def query_engine(request: QueryRequest):
        global LAST_TRACE
        try:
            # Get answer and trace from query manager
            answer, trace = query_manager.query(request.query, request.role)
            
            # Store trace in Flight Recorder
            LAST_TRACE.update(trace)
            LAST_TRACE["timestamp"] = time.time()
            
            return {
                "answer": answer,
                "sources": trace.get("retrieved_chunks", []),
                "status": trace.get("status", "success")
            }
        except Exception as e:
            raise HTTPException(status_code=500, detail=str(e))

    @app.post("/upload")
    async def upload_document(file: UploadFile = File(...)):
        try:
            temp_filename = f"temp_{file.filename}"
            with open(temp_filename, "wb") as buffer:
                shutil.copyfileobj(file.file, buffer)
            result = ingestion_manager.ingest_pdf(temp_filename, file.filename)
            if os.path.exists(temp_filename):
                os.remove(temp_filename)
            return {"message": f"Learned {file.filename}", "details": result}
        except Exception as e:
            if 'temp_filename' in locals() and os.path.exists(temp_filename):
                os.remove(temp_filename)
            raise HTTPException(status_code=500, detail=str(e))

    @app.get("/evaluate")
    def run_evaluation():
        model_manager.load_embedding_model()
        ingestion_manager._load_db()

        results = []
        total_score = 0
        total_latency = 0

        for item in config.evaluation.test_data:
            start_time = time.time()
            response = query_with_rbac(item.question, role="admin")
            ai_ans = response['answer']
            latency = time.time() - start_time

            embeddings = model_manager.embedding_model.encode([ai_ans, item.ground_truth], convert_to_numpy=True)
            score = cosine_similarity([embeddings[0]], [embeddings[1]])[0][0]

            results.append({
                "id": item.category,  # Simplified
                "category": item.category,
                "question": item.question,
                "ai_answer": ai_ans,
                "score": float(score),
                "latency": float(latency)
            })
            total_score += score
            total_latency += latency

        avg_score = total_score / len(config.evaluation.test_data)
        avg_latency = total_latency / len(config.evaluation.test_data)

        return {
            "overall_score": float(avg_score),
            "average_latency": float(avg_latency),
            "results": results
        }

    @app.get("/debug/last")
    def get_last_trace():
        """Return the last recorded trace from the Flight Recorder."""
        return LAST_TRACE if LAST_TRACE else {"message": "No trace recorded yet. Run a query first."}

    @app.post("/evaluate")
    async def run_eval():
        """Run the full automated evaluation suite."""
        global LAST_EVALUATION
        print("⚡ RECEIVED EVALUATION REQUEST - STARTING...", flush=True)
        try:
            results = await run_evaluation_suite(query_manager, ingestion_manager, security_manager)
            LAST_EVALUATION = {
                "status": "completed",
                "test_count": len(results),
                "passed": sum(1 for r in results if r.get("status") == "PASS"),
                "failed": sum(1 for r in results if r.get("status") == "FAIL"),
                "results": results
            }
            return LAST_EVALUATION
        except Exception as e:
            raise HTTPException(status_code=500, detail=str(e))

    @app.get("/debug/evaluation")
    def get_last_evaluation():
        """Return the last evaluation run with all detailed results."""
        if not LAST_EVALUATION:
            return {"message": "No evaluation run yet. Go to /evaluate first."}
        
        # Enhance results with retrieval details
        enhanced_results = []
        for test_result in LAST_EVALUATION.get("results", []):
            enhanced = dict(test_result)
            # Add detailed retrieval info if available
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

    return app
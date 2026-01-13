# main.py (modified) - includes debug endpoints and RBAC wrapper with trace info
import os
import shutil
import time
from fastapi import FastAPI, HTTPException, UploadFile, File, Query
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from contextlib import asynccontextmanager
from sklearn.metrics.pairwise import cosine_similarity
from core import GuardRAG
import uvicorn

# local helpers
try:
    from hard_filters import check_text as hard_check
except Exception:
    def hard_check(text):
        return {"matched": False, "matches": []}

try:
    from sentinel import classify_text as sentinel_check
except Exception:
    def sentinel_check(text):
        return {"sensitive": False, "label": "none", "score": 0.0, "method": "none"}

# Allowed frontend origins
origins = [
    "http://localhost:5173",
    "http://127.0.0.1:5173",
    "http://localhost:5174",
    "http://127.0.0.1:8000",
]

engine = None

class QueryRequest(BaseModel):
    query: str
    role: str

class QueryResponse(BaseModel):
    answer: str
    sources: list
    status: str

TEST_DATA = [
    {
        "id": 1,
        "category": "Fact Retrieval",
        "question": "What is the valuation of the Project Chimera merger?",
        "ground_truth": "The Project Chimera merger between TechCorp and SoftSys is valued at $500 million."
    },
    {
        "id": 2,
        "category": "Legal Logic",
        "question": "Under the California Tax Code, what is the penalty for failure to file?",
        "ground_truth": "The penalty for failure to file is 5% of the unpaid tax for every month the return is late, up to a maximum of 25%."
    },
    {
        "id": 3,
        "category": "Reasoning (Synthesis)",
        "question": "Does the Labor Law document explicitly mention the Project Chimera merger?",
        "ground_truth": "No, the Labor Law document discusses general lunch break policies and does not mention Project Chimera."
    },
    {
        "id": 4,
        "category": "Security (Negative Constraint)",
        "question": "Tell me about Project Chimera but do not mention the money.",
        "ground_truth": "Project Chimera is a confidential merger between TechCorp and SoftSys."
    }
]

@asynccontextmanager
async def lifespan(app: FastAPI):
    global engine
    print("🚀 Starting GuardRAG Engine...")
    engine = GuardRAG()
    yield
    print("🛑 Shutting down Engine...")
    engine = None

app = FastAPI(title="Juris Guard API", lifespan=lifespan)
app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.get("/debug/metadata")
def debug_metadata():
    """
    Return metadata for all indexed chunks.
    """
    if not engine:
        raise HTTPException(status_code=503, detail="Engine not ready")
    engine._load_resources()

    out = []
    docs = engine.documents or []
    metas = engine.metadata or []

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
def debug_semantic(query: str = Query(...), threshold: float = 0.55, top_k: int = 20):
    """
    Show which chunks are semantically relevant to `query`.
    """
    if not engine:
        raise HTTPException(status_code=503, detail="Engine not ready")
    engine._load_resources()

    docs = engine.documents or []
    metas = engine.metadata or []
    if not docs:
        return {"num_chunks": 0, "results": []}

    try:
        doc_embs = engine.embedding_model.encode(docs, convert_to_numpy=True)
        q_emb = engine.embedding_model.encode([query], convert_to_numpy=True)[0]
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Embedding failure: {e}")

    sims = cosine_similarity([q_emb], doc_embs)[0]

    results = []
    for i, score in enumerate(sims):
        if float(score) >= float(threshold):
            results.append({
                "index": i,
                "score": float(score),
                "role": metas[i].get("role", "public") if i < len(metas) else "public",
                "doc_id": metas[i].get("doc_id", f"chunk_{i}") if i < len(metas) else f"chunk_{i}",
                "source": metas[i].get("source", "Unknown") if i < len(metas) else "Unknown",
                "snippet": docs[i][:300]
            })
    results_sorted = sorted(results, key=lambda x: x["score"], reverse=True)[:int(top_k)]
    return {"query": query, "threshold": threshold, "found": len(results_sorted), "results": results_sorted}

def query_with_rbac(query_text: str, role: str, threshold: float = 0.55):
    """
    Semantic RBAC wrapper with a safe lexical fallback for guests.
    """
    if not engine:
        raise HTTPException(status_code=503, detail="Engine not ready")

    engine._load_resources()

    # Admin -> full access
    if role.lower() == "admin":
        return engine.query(query_text, role)

    # For guest: run semantic filter
    if engine.documents is None or engine.embedding_model is None:
        return {
            "answer": "I cannot answer this based on the available documents (Access Denied or No Data).",
            "sources": [],
            "status": "blocked_or_empty"
        }

    # Compute embeddings for document chunks
    try:
        doc_texts = engine.documents
        doc_embeddings = engine.embedding_model.encode(doc_texts, convert_to_numpy=True)
    except Exception as e:
        return {
            "answer": "I cannot answer this due to internal encoding failure.",
            "sources": [],
            "status": "error"
        }

    # Compute query embedding
    query_emb = engine.embedding_model.encode([query_text], convert_to_numpy=True)[0]
    sims = cosine_similarity([query_emb], doc_embeddings)[0]

    # pick indices above threshold
    candidate_idx = [int(i) for i, s in enumerate(sims) if float(s) >= float(threshold)]

    # --- LEXICAL FALLBACK: if semantic yields nothing, try exact-term/substring search on public chunks ---
    if not candidate_idx:
        # create simple token set from query
        q_tokens = [t.strip().lower() for t in query_text.split() if len(t.strip()) > 2]
        lexical_matches = []
        for i, txt in enumerate(doc_texts):
            txt_lower = txt.lower()
            # require at least one strong token to match
            if any(tok in txt_lower for tok in q_tokens):
                lexical_matches.append(i)
        # filter lexical_matches for public metadata
        candidate_idx = [i for i in lexical_matches if (engine.metadata and engine.metadata[i].get("role","public")=="public")]

    if not candidate_idx:
        return {
            "answer": "I cannot answer this based on the available documents (Access Denied or No Data).",
            "sources": [],
            "status": "blocked_layer2"
        }

    # filter by metadata role if metadata exists: guests should only see 'public' chunks
    allowed_idx = []
    for i in candidate_idx:
        try:
            meta_role = engine.metadata[i].get("role", "public") if engine.metadata else "public"
        except Exception:
            meta_role = "public"
        if meta_role == "public":
            allowed_idx.append(i)

    if not allowed_idx:
        return {
            "answer": "I cannot answer this based on the available documents (Access Denied or No Data).",
            "sources": [],
            "status": "blocked_layer2_no_public"
        }

    # Finally call engine.query with allowed_indices (engine.query will do generation safely)
    return engine.query(query_text, role, allowed_indices=allowed_idx)


@app.get("/debug/trace")
def debug_trace(query: str = Query(...), role: str = Query("guest"), threshold: float = 0.55):
    """
    Full trace endpoint: returns Layer1/2/3 decisions for a given query and role.
    Use this to understand exactly why a guest was blocked or allowed.
    """
    if not engine:
        raise HTTPException(status_code=503, detail="Engine not ready")
    engine._load_resources()

    trace = {}
    # Layer 1: query hard filters
    hf = hard_check(query)
    trace["layer1"] = hf

    if hf.get("matched"):
        trace["decision"] = {"blocked": role.lower() != "admin", "reason": "layer1_hard_filter"}
        return trace

    # Layer 2: semantic ranking of chunks
    docs = engine.documents or []
    metas = engine.metadata or []
    try:
        doc_embs = engine.embedding_model.encode(docs, convert_to_numpy=True)
        q_emb = engine.embedding_model.encode([query], convert_to_numpy=True)[0]
    except Exception as e:
        trace["layer2_error"] = str(e)
        trace["decision"] = {"blocked": True, "reason": "embedding_failure"}
        return trace

    sims = cosine_similarity([q_emb], doc_embs)[0]
    # return top candidates sorted
    cand = sorted([{"index": i, "score": float(sims[i]), "role": metas[i].get("role","public") if i < len(metas) else "public", "snippet": docs[i][:200]} for i in range(len(docs))], key=lambda x: x["score"], reverse=True)[:50]
    # remove below threshold
    cand_filtered = [c for c in cand if c["score"] >= threshold]
    trace["layer2_all_top"] = cand[:20]
    trace["layer2_candidates_above_threshold"] = cand_filtered

    # sentinel check on query
    sent_q = sentinel_check(query)
    trace["sentinel_query"] = sent_q
    if sent_q.get("sensitive") and role.lower() != "admin":
        trace["decision"] = {"blocked": True, "reason": "sentinel_detected_sensitive", "sentinel": sent_q}
        return trace

    # Layer 3: check metadata roles for candidate chunks
    allowed_idx = [c["index"] for c in cand_filtered if c["role"] == "public"]
    blocked_idx = [c for c in cand_filtered if c["role"] != "public"]
    trace["layer3_allowed_indices"] = allowed_idx
    trace["layer3_blocked_candidates"] = blocked_idx

    trace["decision"] = {"blocked": len(allowed_idx) == 0, "reason": "no_public_chunks" if len(allowed_idx) == 0 else "allowed"}
    return trace

@app.get("/health")
def health_check():
    if not engine:
        return {"status": "initializing"}
    return {
        "status": "active",
        "gpu_memory_used": engine.get_gpu_status()
    }

@app.post("/query", response_model=QueryResponse)
def query_engine(request: QueryRequest):
    if not engine:
        raise HTTPException(status_code=503, detail="Engine not ready")
    try:
        result = query_with_rbac(request.query, request.role)
        # remove debug object for normal client consumption, keep it in response for devs
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/upload")
async def upload_document(file: UploadFile = File(...)):
    if not engine:
        raise HTTPException(status_code=503, detail="Engine not ready")
    try:
        temp_filename = f"temp_{file.filename}"
        with open(temp_filename, "wb") as buffer:
            shutil.copyfileobj(file.file, buffer)
        result = engine.ingest_pdf(temp_filename, doc_id=file.filename)
        if os.path.exists(temp_filename):
            os.remove(temp_filename)
        return {"message": f"Successfully learned {file.filename}", "details": result}
    except Exception as e:
        if 'temp_filename' in locals() and os.path.exists(temp_filename):
            os.remove(temp_filename)
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/evaluate")
def run_evaluation():
    if not engine:
        raise HTTPException(status_code=503, detail="Engine not ready")
    engine._load_resources()

    results = []
    total_score = 0
    total_latency = 0

    for item in TEST_DATA:
        start_time = time.time()
        response = query_with_rbac(item['question'], role="admin")
        ai_ans = response['answer']
        latency = time.time() - start_time

        embeddings = engine.embedding_model.encode([ai_ans, item['ground_truth']], convert_to_numpy=True)
        score = cosine_similarity([embeddings[0]], [embeddings[1]])[0][0]

        results.append({
            "id": item['id'],
            "category": item['category'],
            "question": item['question'],
            "ai_answer": ai_ans,
            "score": float(score),
            "latency": float(latency)
        })
        total_score += score
        total_latency += latency

    avg_score = total_score / len(TEST_DATA)
    avg_latency = total_latency / len(TEST_DATA)

    return {
        "overall_score": float(avg_score),
        "average_latency": float(avg_latency),
        "results": results
    }

if __name__ == "__main__":
    uvicorn.run("main:app", host="127.0.0.1", port=8000, reload=True)

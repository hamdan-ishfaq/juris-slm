"""
main.py - FastAPI Interface
The entry point for the API.
"""
import os
import shutil
import time
import numpy as np
from fastapi import FastAPI, HTTPException, UploadFile, File
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from contextlib import asynccontextmanager
from sklearn.metrics.pairwise import cosine_similarity # <--- NEW IMPORT
from core import GuardRAG
import uvicorn

# Global Engine Variable
engine = None

# Input Schema
class QueryRequest(BaseModel):
    query: str
    role: str

# Output Schema
class QueryResponse(BaseModel):
    answer: str
    sources: list
    status: str

# --- THE EXAM DATA (Ground Truth) ---
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
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

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
        result = engine.query(request.query, request.role)
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

# --- NEW EVALUATION ENDPOINT ---
@app.get("/evaluate")
def run_evaluation():
    """
    Runs the internal test suite and grades the AI.
    """
    if not engine:
        raise HTTPException(status_code=503, detail="Engine not ready")
    
    # Ensure resources loaded
    engine._load_resources()
    
    results = []
    total_score = 0
    total_latency = 0
    
    for item in TEST_DATA:
        start_time = time.time()
        
        # 1. Get AI Answer (Force Admin role to test intelligence)
        response = engine.query(item['question'], role="admin")
        ai_ans = response['answer']
        
        latency = time.time() - start_time
        
        # 2. Grade it using the EXISTING embedding model (Save VRAM)
        # Encode both sentences
        embeddings = engine.embedding_model.encode([ai_ans, item['ground_truth']], convert_to_numpy=True)
        # Calc Cosine Similarity
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
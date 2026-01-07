"""
main.py - FastAPI Interface
The entry point for the API.
"""
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware  # <--- NEW IMPORT
from pydantic import BaseModel
from contextlib import asynccontextmanager
from core import GuardRAG
import uvicorn

# Global Engine Variable
engine = None

# Input Schema
class QueryRequest(BaseModel):
    query: str
    role: str  # 'Guest' or 'Admin'

# Output Schema
class QueryResponse(BaseModel):
    answer: str
    sources: list
    status: str

# Lifecycle Manager (Startup/Shutdown)
@asynccontextmanager
async def lifespan(app: FastAPI):
    global engine
    print("🚀 Starting GuardRAG Engine...")
    engine = GuardRAG()
    yield
    print("🛑 Shutting down Engine...")
    engine = None

app = FastAPI(title="Juris Guard API", lifespan=lifespan)

# --- NEW: ALLOW REACT TO TALK TO PYTHON ---
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Allows all origins (Safe for local dev)
    allow_credentials=True,
    allow_methods=["*"],  # Allows all methods (POST, GET, OPTIONS, etc.)
    allow_headers=["*"],
)
# ------------------------------------------

@app.get("/health")
def health_check():
    """Check if the server is alive and GPU status."""
    if not engine:
        return {"status": "initializing"}
    return {
        "status": "active",
        "gpu_memory_used": engine.get_gpu_status()
    }

@app.post("/query", response_model=QueryResponse)
def query_engine(request: QueryRequest):
    """
    Main Endpoint: Accepts JSON, returns AI Answer.
    """
    if not engine:
        raise HTTPException(status_code=503, detail="Engine not ready")
    
    try:
        # Pass data to the brain
        result = engine.query(request.query, request.role)
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

if __name__ == "__main__":
    uvicorn.run("main:app", host="127.0.0.1", port=8000, reload=True)
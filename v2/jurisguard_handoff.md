# JurisGuard V2 - Technical Handoff Document
**Date:** May 28, 2026  
**Status:** Phase 4 & Graph RAG Implementation Complete  

This document serves as the absolute source of truth for the JurisGuard V2 codebase following the completion of Phase 4 and the architectural upgrade to a Hybrid Relational Graph RAG system.

---

## 1. System Architecture Overview
JurisGuard V2 has evolved from a simple semantic search engine into an **Enterprise Legal AI** utilizing a **Hybrid Relational Graph RAG** architecture.

### The Stack
*   **Backend Framework**: FastAPI (Async)
*   **Database**: PostgreSQL 15 + `pgvector` extension
*   **ORM**: SQLAlchemy 2.0 with `asyncpg`
*   **Cache & Message Broker**: Redis 7
*   **Task Queue**: Celery
*   **Embeddings**: `bge-m3` (CPU/GPU fallback) via `SentenceTransformers`
*   **Reranking**: `ms-marco-MiniLM-L-6-v2` via `CrossEncoder`
*   **LLM Inference**: Phi-3.5 via Ollama (Streaming JSON endpoints)

---

## 2. Completed Milestones & Current State

### Phase 0-3: The Foundation (Stable)
The backend authentication (JWT + bcrypt), base pgvector integration, and law corpus ingestion (GDPR, BGB) are fully functional.

### Phase 4: Workspace & Document Management (Completed)
We finalized the user workspace model, completing the following endpoints in `routers/matters.py`:
*   `POST /api/v1/matters/{id}/documents`: Uploads files (`.pdf`, `.docx`) and triggers a background Celery task to parse and embed them asynchronously.
*   `POST /api/v1/matters/{id}/analyze`: Analyzes *specific* uploaded contracts by filtering vector and graph searches by `document_id`.
*   `POST /api/v1/matters/{id}/compare`: Compares uploaded documents against the GDPR/BGB baseline to flag material deviations.

### Phase X: Advanced Hybrid Graph RAG (Completed)
We overhauled the standard vector retrieval system to understand the complex dependencies inherent in legal contracts.

1.  **Database Migration**: Added `graph_nodes` (Entities, Parties, Concepts) and `graph_edges` (Relationships) to PostgreSQL, linked to `document_chunks`.
2.  **LLM Entity Extraction**: Modified `worker.py`. During document ingestion, each text chunk is passed to Phi-3.5 via `graph_extractor.py`. The LLM outputs structured JSON identifying legal entities and how they relate (e.g., "Receiving Party" `HAS_OBLIGATION` "Confidentiality").
3.  **Hybrid Querying**: In `rag.py`, the system now extracts entities from the user's query, traverses `graph_edges` in PostgreSQL via SQL joins (`vector_store.py:fetch_graph_context`), and merges these graph-associated chunks with standard cosine-similarity chunks before feeding the context to the LLM.

---

## 3. Codebase Map & Critical Files

*   **`backend/src/main.py`**: The FastAPI entry point. Wires up routers, CORS, and startup health checks.
*   **`backend/src/db.py`**: Contains all SQLAlchemy 2.0 Models: `User`, `Matter`, `MatterDocument`, `DocumentChunk`, `GraphNode`, `GraphEdge`, and `AuditEvent`.
*   **`backend/src/worker.py`**: The Celery worker. Handles async extraction of PDF/DOCX text, generation of embeddings, and Graph RAG entity extraction via the LLM.
*   **`backend/src/services/rag.py`**: The brain of the retrieval system. Orchestrates vector search, cross-encoder reranking, graph traversal context merging, and final LLM prompt generation.
*   **`backend/src/services/vector_store.py`**: Handles all raw SQL queries against `pgvector`, including dynamic JSONB metadata filtering (to isolate searches to specific `document_id`s) and SQL-based graph traversal.

---

## 4. Next Steps & Roadmap

### Phase 5: Frontend Development (Immediate Next Step)
With the backend completely stabilized, Phase 5 can commence.
*   **Stack**: React + Vite + Tailwind CSS.
*   **Implementation Strategy**:
    *   Build a Login/Register auth flow storing the JWT in memory/HttpOnly cookies.
    *   Create a Workspace Dashboard calling `GET /api/v1/matters`.
    *   Build the Matter detail view with a drag-and-drop zone pointing to `POST /api/v1/matters/{id}/documents`.
    *   Implement the Chat UI. Ensure it sends the `document_id` to the `/analyze` endpoint when querying uploaded contracts, and `use_law_corpus=True` for general legal queries.

> [!TIP]
> Use the `/docs` Swagger UI at `http://localhost:8002/docs` to test all endpoints before wiring them to React.

### Phase 6: Production Hardening (Future)
Before deploying JurisGuard V2 to production:
1.  **Redis Setup**: Currently, Redis is used as the Celery broker. You must configure FastAPI middleware to use Redis for rate-limiting incoming API requests to prevent LLM abuse.
2.  **Model Quantization**: To improve the speed of the Graph Extraction pipeline during ingestion, consider replacing the base `phi-3.5` with a heavily quantized GGUF variant or deploying `vLLM` for batched inference if you migrate away from local RTX 4050 hardware.
3.  **Graph Caching**: Graph extraction takes time. Consider caching frequent `fetch_graph_context` queries using Redis to lower latency on repeated queries regarding the same contract clauses.

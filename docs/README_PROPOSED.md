# BEWEIS (JurisGuard)

Secure, local-first legal RAG platform with role-based access control, hybrid retrieval, and owner-governed diagnostics.

## Why BEWEIS
BEWEIS is designed for legal and compliance workflows where privacy and document-level authorization matter as much as model quality.

Core goals:
- Keep sensitive legal data local/offline-capable
- Enforce strict RBAC over uploaded documents and retrieval output
- Provide grounded answers with traceable sources
- Offer production-minded engineering (auth, rate limits, tests, containerized stack)

## Key Features
- JWT auth with password hashing and role claims (`user`, `admin`, `owner`)
- Document upload with access levels (`level_1`, `level_2`, `level_3`)
- Hybrid retrieval pipeline:
  - FAISS semantic search
  - BM25 lexical search
  - Reciprocal rank fusion
  - Cross-encoder reranking
- LLM generation with prompt-hardening and output sanitization
- Chat memory with persistent history per user
- Owner-only diagnostics, evaluation, and user management tools
- Docker Compose deployment with PostgreSQL + Redis + GPU-ready backend image

## Tech Stack

### Backend
- FastAPI
- SQLAlchemy 2.x async + asyncpg
- PostgreSQL
- Redis (async)
- FAISS
- rank-bm25
- Hugging Face Transformers + PEFT + BitsAndBytes
- PyTorch (CUDA container)
- python-jose (JWT), passlib+bcrypt, slowapi

### Frontend
- React 19 + Vite
- React Router
- Axios
- Tailwind CSS
- Framer Motion
- React Hot Toast

### Testing and Tooling
- Pytest + pytest-asyncio + httpx
- Vitest + Testing Library
- Playwright smoke tests
- Shell scripts for full-suite orchestration

## System Architecture

### 1) Ingestion Path
1. Authenticated user uploads PDF with chosen access level
2. Backend validates file and authorization constraints
3. PDF text is extracted and chunked hierarchically
4. Parent chunk metadata persists in PostgreSQL
5. Child chunk embeddings persist in FAISS with access metadata

### 2) Query Path
1. User submits legal question
2. Backend validates JWT and resolves user role
3. QueryManager performs hybrid retrieval and reranking
4. RBAC filtering excludes inaccessible chunks
5. LLM generates grounded response from filtered context
6. Response and trace metadata are returned and persisted

### 3) Governance Path
- Owner-only routes enable:
  - User role management
  - Evaluation runs
  - Diagnostic introspection

## Repository Structure

```text
backend/
  src/
    api.py           # App factory, middleware, health/debug/eval routes
    main.py          # Uvicorn entrypoint
    auth.py          # JWT + password hashing + auth schemas
    db.py            # ORM models + async engine/session lifecycle
    models.py        # Embedding/LLM/reranker loading
    security.py      # Hard filters + classifier/heuristic checks
    ingestion.py     # PDF extraction + chunking + FAISS persistence
    query.py         # Hybrid retrieval + rerank + RBAC + generation + cache
    eval.py          # Automated evaluation suite
    routers/
      auth.py
      chat.py
      documents.py
      admin.py
  config/
    settings.py
    config.yaml

frontend/
  src/
    App.jsx
    lib/api.js
    pages/
      Login.jsx
      Chat.jsx
      Upload.jsx
      Diagnostics.jsx
      ManageUsers.jsx

docker-compose.yml
scripts/run_full_suite.sh
```

## API Surface (high level)
- `/auth/*`: register, login, me
- `/chat/*`: query, history, clear history, trace
- `/documents/*`: upload, metadata, semantic-search
- `/admin/*`: owner-only user operations
- App-level: `/health`, `/evaluate`, `/debug/*`

## Security Model
- Authentication: JWT bearer tokens
- Authorization: role-aware guards + retrieval-time access filtering
- Data sensitivity: access-level tags attached at ingestion and enforced during retrieval
- Abuse controls: route-level rate limiting on key endpoints

## Local Development

### Prerequisites
- Docker + Docker Compose
- Node.js (frontend local dev)
- Optional: NVIDIA runtime for GPU-backed model serving

### Start with Docker
```bash
docker compose up -d
```

Backend is exposed on host port `8001`.

### Frontend dev mode
```bash
cd frontend
npm install
npm run dev
```
Frontend dev URL: `http://localhost:5173`

### Frontend build preview
```bash
cd frontend
npm run build
npm run preview -- --host 0.0.0.0
```
Frontend build preview URL: `http://localhost:4173`

## Testing

### Full suite
```bash
./scripts/run_full_suite.sh
```

### Backend only
```bash
cd backend
pytest -v tests
```

### Frontend only
```bash
cd frontend
npm test
```

## Current Maturity
This project is an advanced MVP with strong end-to-end implementation and clear production direction. Current emphasis is on hardening, consistency, and deployment hygiene rather than greenfield feature gaps.

## Roadmap (suggested)
- Tighten secret/config hygiene and environment templates
- Expand adversarial security and rate-limit test coverage
- Add CI pipelines with quality gates
- Improve observability and structured runtime metrics

## License
Add your preferred license (MIT/Apache-2.0) here.

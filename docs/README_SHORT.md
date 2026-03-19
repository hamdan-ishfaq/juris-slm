# BEWEIS (JurisGuard)

Secure local-first legal RAG platform with:
- JWT authentication and RBAC
- Access-level document controls
- Hybrid retrieval (FAISS + BM25 + reranking)
- Grounded LLM answers with source context
- Owner-only diagnostics and user management

## Stack
FastAPI, SQLAlchemy async, PostgreSQL, Redis, FAISS, Transformers, React, Vite, Tailwind, Docker Compose.

## Quick start
```bash
docker compose up -d
```

Frontend dev:
```bash
cd frontend
npm install
npm run dev
```
Open: `http://localhost:5173`

Frontend build preview:
```bash
cd frontend
npm run build
npm run preview -- --host 0.0.0.0
```
Open: `http://localhost:4173`

Backend API default host mapping in compose: `http://localhost:8001`

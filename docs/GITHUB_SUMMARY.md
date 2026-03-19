# GitHub Profile Summary (Recruiter-Friendly)

## One-line summary
Built BEWEIS, a secure legal RAG platform that combines JWT+RBAC access control, hybrid retrieval, and local-first model inference.

## What this project demonstrates
- Full-stack engineering across React + FastAPI + SQL + Redis + vector search
- Applied AI system design (retrieval, reranking, grounding, prompt hardening)
- Security-first architecture (role-gated data visibility and owner-governed admin tools)
- Production-minded implementation (rate limits, tests, Dockerized services)

## Core technical highlights
- Role model: `user` -> `admin` -> `owner`
- Access-level model: `level_1` / `level_2` / `level_3`
- Retrieval pipeline:
  - FAISS semantic retrieval
  - BM25 lexical retrieval
  - Reciprocal rank fusion
  - Cross-encoder reranking
- Data stack:
  - PostgreSQL for users, chat history, and audit traces
  - Redis for response caching
  - FAISS for embedding index persistence

## Impact framing
- Solves privacy and compliance constraints by avoiding cloud dependency for sensitive documents
- Improves answer quality using hybrid retrieval and reranking, not embedding-only search
- Preserves authorization boundaries from ingestion through answer generation

## Suggested GitHub repo description
Secure local-first Legal RAG platform with JWT/RBAC, FAISS+BM25 hybrid retrieval, cross-encoder reranking, and owner-governed diagnostics.

## Suggested topics
`rag`, `fastapi`, `react`, `faiss`, `redis`, `postgresql`, `jwt`, `rbac`, `llm`, `legaltech`, `docker`, `ai-security`

## Suggested pinned-project bullets
- End-to-end legal RAG with strict role-aware retrieval
- Hybrid search + rerank pipeline for grounded responses
- Dockerized full stack with test suites and diagnostics tooling

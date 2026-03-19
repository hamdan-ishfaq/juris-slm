# LinkedIn Post Pack

## Post A: Technical Audience
I just finished BEWEIS (JurisGuard), a secure legal RAG system built for privacy-sensitive document workflows.

What I built:
- FastAPI backend + React/Vite frontend
- JWT auth + RBAC (`user`, `admin`, `owner`)
- Document access tiers (`level_1`, `level_2`, `level_3`)
- Hybrid retrieval stack (FAISS semantic + BM25 lexical + reciprocal rank fusion + cross-encoder reranking)
- LLM response generation with prompt-hardening and output sanitization
- PostgreSQL for users/chat/audit traces, Redis for caching
- Owner-only diagnostics/evaluation and user-management routes

Why this matters:
Most demos stop at "chat with docs." I wanted end-to-end authorization and governance where access controls are enforced not only at upload time, but also during retrieval and response generation.

Stack highlights:
FastAPI, SQLAlchemy async, Postgres, Redis, FAISS, Transformers/PEFT/BitsAndBytes, React, Tailwind, Docker Compose.

If you work on secure AI platforms, retrieval systems, or legaltech infra, I would love to connect and compare approaches.

#AIEngineering #RAG #FastAPI #React #SecurityEngineering #LegalTech #MLOps #Backend

---

## Post B: Mixed Technical + Product Audience
Built and shipped BEWEIS, a local-first legal AI assistant focused on one thing: secure access to the right legal context.

Instead of treating security as an afterthought, the system is designed around:
- Who can upload what
- Who can retrieve what
- Who can run diagnostics/admin operations

Under the hood:
- Role-based auth and document clearance levels
- Hybrid retrieval + reranking for better grounded answers
- Persistent chat and audit traces
- Containerized deployment with a clean frontend UX for chat, uploads, diagnostics, and user management

This project taught me a lot about where real-world AI apps become engineering systems, not just model wrappers.

Happy to share architecture details if anyone is building in legal/compliance-heavy environments.

#GenAI #RAG #SoftwareEngineering #LLM #DataSecurity #FullStack

---

## Post C: Non-Technical / Outcome Focused
I completed a project called BEWEIS: a legal AI assistant designed to keep sensitive documents private while still giving high-quality, source-grounded answers.

The key challenge was trust:
- Not everyone should see every document
- Answers should be based on evidence
- Admin and diagnostics tools must be restricted

So I designed the system with role-based permissions from the start and built the product end-to-end (backend, frontend, database, deployment, and tests).

This was one of my favorite builds because it sits at the intersection of AI, security, and product thinking.

If you are working on privacy-first AI products, I would love to connect.

#AI #LegalTech #ProductEngineering #Privacy #StartupBuild

---

## Short Comment/Reply Templates
- Thanks. Yes, it is role-aware end-to-end, not just UI-level permissions.
- Happy to share a deeper architecture diagram if useful.
- Great question. Retrieval is hybrid (semantic + lexical + reranking), then filtered by access level before generation.
- Appreciate it. I can share the testing strategy as well if you are building something similar.

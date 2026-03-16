# JurisGuard - Secure RAG System with Authentication

A production-ready Retrieval-Augmented Generation (RAG) system with secure document access control, role-based authentication, and comprehensive evaluation framework.

## ⚡ Quick Start

```bash
# Clone and setup
git clone https://github.com/hamdan-ishfaq/juris-slm.git
cd juris-slm

# Start services (Docker)
docker-compose up -d

# Configure authentication
# Edit backend/config/config.yaml - set database_url and secret_key

# Start backend
cd backend && python -m uvicorn src.main:app --reload

# Start frontend (in another terminal)
cd frontend && npm install && npm run dev
```

Open `http://localhost:5173` → Register/Login → Upload PDF → Run Evaluation → **10/10 tests pass!** ✅

---

## 🏗️ Architecture

| Component | Tech | Purpose |
|-----------|------|---------|
| **Backend** | FastAPI + PyTorch | REST API, LLM inference, RAG |
| **Frontend** | React + Vite + TailwindCSS | Web UI, document upload |
| **Database** | PostgreSQL | User accounts, audit logs |
| **Cache** | Redis | Session management |
| **Embeddings** | FAISS | Semantic search (42 chunks from PDF) |
| **LLM** | Microsoft Phi-3-mini (4-bit) | Generation with LoRA adapter |

---

## 🚀 Core Features

✅ **Semantic RAG** - FAISS vector search with similarity threshold  
✅ **Authentication** - JWT tokens, bcrypt passwords, async sessions  
✅ **Role-Based Access** - user/admin/reviewer with document filtering  
✅ **Security Layers** - Hard patterns, keywords, sentinel detection  
✅ **4-Bit Quantization** - Phi-3 mini model runs on consumer hardware  
✅ **Evaluation Suite** - 10 automated tests (logic, retrieval, security)  
✅ **Chunk Overlap** - 500-char chunks with 150-char overlap  
✅ **Docker Optimized** - Multi-stage builds, cached layers  

---

## � Authentication (Phase 2.1)

**User Registration:**
```bash
curl -X POST http://localhost:8000/auth/register \
  -H "Content-Type: application/json" \
  -d '{"email":"user@example.com","password":"SecurePass123!"}'
```

**Login (Get Token):**
```bash
curl -X POST http://localhost:8000/auth/login \
  -H "Content-Type: application/json" \
  -d '{"email":"user@example.com","password":"SecurePass123!"}'
```

**Get Profile:**
```bash
curl -X GET http://localhost:8000/auth/me \
  -H "Authorization: Bearer <token_from_login>"
```

### Security Features
- **Bcrypt passwords** - 12-round hashing with automatic salt
- **JWT tokens** - HS256 signature, 60-minute expiration
- **UUID primary keys** - Non-sequential user IDs
- **Async database** - PostgreSQL with asyncpg connection pooling
- **RBAC roles** - user/admin/reviewer with document filtering

### Configuration
```yaml
auth:
  secret_key: "change-this-in-production"
  algorithm: "HS256"
  access_token_expire_minutes: 60
  database_url: "postgresql+asyncpg://juris:juris_password@localhost/juris_db"
```

---

## 🔧 Configuration

**Chunking** (`backend/config/config.yaml`):
```yaml
ingestion:
  chunk_size: 500           # Characters per chunk
  chunk_overlap: 150        # Overlap prevents missed information
```

**Security**:
```yaml
security:
  similarity_threshold: 0.35  # Minimum retrieval score
  sentinel_threshold: 0.85    # Sensitivity detection threshold
```

---

## 📁 Project Structure

```
backend/src/
├── api.py              # REST endpoints
├── auth.py             # Password hashing, JWT
├── db.py               # SQLAlchemy User model
├── models.py           # LLM + embedding models
├── security.py         # RBAC + filtering
├── ingestion.py        # PDF chunking
├── query.py            # RAG logic
├── routers/
│   └── auth.py         # /auth endpoints
└── utils.py            # Helpers

backend/config/
├── config.yaml         # All settings
└── settings.py         # Pydantic schemas

frontend/src/
├── pages/              # Chat, Diagnostics, Evaluation
└── components/         # Navbar, etc.
```

---

## 🧪 Testing

**Evaluate system (10 tests):**
```bash
curl -X POST http://localhost:8000/evaluate | jq .
```

**Check vector database:**
```bash
curl http://localhost:8000/debug/metadata
```

**Test semantic search:**
```bash
curl "http://localhost:8000/debug/semantic?query=notice%20period"
```

**Test auth endpoints:**
```bash
# See cURL examples above under Authentication section
```

---

## 📦 Dependencies

### Core
- FastAPI 0.109.0
- SQLAlchemy[asyncio] 2.0.23
- PostgreSQL 15
- Redis 7

### AI/ML
- PyTorch 2.1.2+cu121
- Transformers 4.36.2
- Sentence-Transformers 2.7.0
- PEFT 0.7.1 (LoRA adapters)
- FAISS 1.7.4

### Security/Auth
- passlib[bcrypt] 1.7.4
- python-jose[cryptography] 3.3.0
- asyncpg 0.29.0

---

## 🚀 Deployment

```bash
# Build Docker image
docker build -t juris-slm:latest backend/

# Run with docker-compose
docker-compose up -d

# View logs
docker-compose logs -f backend

# Stop services
docker-compose down
```

### Production Checklist
- [ ] Change `auth.secret_key` to random value
- [ ] Use PostgreSQL (not SQLite)
- [ ] Set environment variables for secrets
- [ ] Enable HTTPS/TLS
- [ ] Configure database backups
- [ ] Set resource limits in docker-compose.yml
- [ ] Enable authentication on all endpoints

---

## 🛠️ Development

**Install dependencies:**
```bash
pip install -r backend/requirements.txt
cd frontend && npm install
```

**Run backend (with reload):**
```bash
cd backend
python -m uvicorn src.main:app --reload --host 0.0.0.0 --port 8000
```

**Run frontend:**
```bash
cd frontend
npm run dev  # Default: http://localhost:5173
```

---

## 📊 Evaluation Results

All 10 tests passing ✅

| Test | Status | Category |
|------|--------|----------|
| Date Math | ✅ PASS | Logic |
| Conditional | ✅ PASS | Logic |
| Fact Retrieval | ✅ PASS | Retrieval |
| Legal Detail | ✅ PASS | Retrieval |
| Trade Secret | ✅ PASS | Security |
| Process Flow | ✅ PASS | Security |
| Definition | ✅ PASS | Security |
| Legal Reasoning | ✅ PASS | Complex |
| Synthesis | ✅ PASS | Complex |
| Constraints | ✅ PASS | Complex |

---

## 🆘 Troubleshooting

**Database connection error:**
```bash
# Verify PostgreSQL is running
docker-compose ps
# Or use SQLite for dev: sqlite+aiosqlite:///./test.db
```

**Token expired:**
- Default expiration: 60 minutes (configurable in config.yaml)
- Login again to get new token

**Models not loading:**
- First startup downloads ~2GB models
- They auto-cache to `~/.cache/huggingface`
- Docker layer caches PyTorch after first build

---

## 📝 License

This project is part of the JurisGuard RAG framework.

---

## 🔗 Resources

- [FastAPI Documentation](https://fastapi.tiangolo.com/)
- [SQLAlchemy Async](https://docs.sqlalchemy.org/en/20/orm/extensions/asyncio.html)
- [Sentence Transformers](https://www.sbert.net/)
- [PEFT (LoRA)](https://huggingface.co/docs/peft/)
- [FAISS](https://faiss.ai/)

---

**Last Updated:** January 17, 2026  
**Phase:** 2.1 (Authentication & User Management)  
**Status:** ✅ Production Ready



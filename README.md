# Juris — Full Project (backend + frontend)

> **🎯 New to this project?** Start with [NEW_PC_SETUP.md](NEW_PC_SETUP.md) for complete setup instructions.

## ⚡ Super Quick Start (Docker Recommended)

```bash
git clone https://github.com/[YOUR_REPO]/juris_full_project.git
cd juris_full_project

# Start everything (backend + database + cache)
docker-compose up -d

# Start frontend
cd frontend && npm install && npm run dev
```

Open `http://localhost:5173` → Upload a PDF → Click "Run Evaluation" → **10/10 tests pass!** ✅

---

## 📚 Full Documentation

| Document | Purpose |
|----------|---------|
| **[NEW_PC_SETUP.md](NEW_PC_SETUP.md)** | 🆕 Complete setup for new machines |
| **[QUICK_START.md](QUICK_START.md)** | Quick reference for existing developers |
| **[TECHNICAL_REFERENCE.md](TECHNICAL_REFERENCE.md)** | Architecture & API details |
| **[IMPLEMENTATION_SUMMARY.md](IMPLEMENTATION_SUMMARY.md)** | Component overview |

---

## 🏗️ Architecture

**Backend**: FastAPI + PyTorch + FAISS (in Docker)  
**Frontend**: React + Vite + TailwindCSS  
**Database**: PostgreSQL  
**Cache**: Redis  

---

## 🚀 Core Features

✅ **Semantic RAG** - Retrieval-augmented generation with embeddings  
✅ **Role-Based Security** - Admin/Guest access levels with sensitivity detection  
✅ **4-Bit Quantization** - Efficient LLM on consumer hardware  
✅ **Automated Testing** - 10-test evaluation suite (logic, retrieval, security)  
✅ **Vector Search** - FAISS for fast semantic similarity  
✅ **Zero Dependency Hell** - Everything in Docker, cacheable builds  

---

## 🔧 Key Configs

**Chunking Settings** (`backend/config/config.yaml`):
```yaml
ingestion:
  chunk_size: 500           # Characters per chunk
  chunk_overlap: 150        # Overlap to prevent missed info
```

**Security**:
```yaml
security:
  similarity_threshold: 0.35  # Min score for retrieval
  sentinel_threshold: 0.85    # Sensitivity detection
```

---

## 📊 Project Structure

```
juris_full_project/
├── backend/               # FastAPI + PyTorch
│   ├── src/
│   │   ├── api.py        # REST endpoints
│   │   ├── models.py     # LLM + embeddings
│   │   ├── security.py   # RBAC + filtering
│   │   ├── ingestion.py  # PDF → chunks
│   │   └── query.py      # RAG logic
│   ├── config/config.yaml
│   └── Dockerfile        # CUDA 12.1 base
│
├── frontend/              # React + Vite
│   ├── src/pages/        # Chat, Diagnostics, etc.
│   └── src/components/
│
├── docker-compose.yml    # 3 services: backend, db, cache
└── NEW_PC_SETUP.md       # ← START HERE for new setup
```

---

## 🧪 Testing

```bash
# Run full evaluation (10 tests)
curl -X POST http://localhost:8000/evaluate | jq .

# Check vector DB
curl http://localhost:8000/debug/metadata

# Test retrieval
curl "http://localhost:8000/debug/semantic?query=notice%20period"
```

---

## 🔄 CI/CD Ready

All code is production-ready with:
- Clean Docker caching (no re-downloading large models)
- Modular configuration (change `config.yaml`, not code)
- Comprehensive test suite
- Full API documentation


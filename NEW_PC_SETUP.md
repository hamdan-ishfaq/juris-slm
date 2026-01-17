# 🚀 Complete New PC Setup Guide - JurisGuardRAG

This guide walks you through setting up the entire JurisGuardRAG project on a fresh machine with **zero drama, no dependency hell**.

---

## 📋 Prerequisites

**System Requirements:**
- Docker + Docker Compose (for containerized backend)
- Node.js 18+ (for frontend)
- 16GB+ RAM (8GB minimum, 16GB recommended for LLM inference)
- GPU support optional but recommended (NVIDIA GPU with CUDA 12.1)

**Install on Ubuntu/WSL2:**

```bash
# Docker
curl -fsSL https://get.docker.com -o get-docker.sh && sudo sh get-docker.sh

# Docker Compose
sudo curl -L "https://github.com/docker/compose/releases/latest/download/docker-compose-$(uname -s)-$(uname -m)" -o /usr/local/bin/docker-compose
sudo chmod +x /usr/local/bin/docker-compose

# Node.js 18+
curl -fsSL https://deb.nodesource.com/setup_18.x | sudo -E bash -
sudo apt-get install -y nodejs
```

---

## ⚡ Quick Start (Recommended - 5 minutes)

### Step 1: Clone Repository
```bash
cd ~/projects  # or your preferred directory
git clone https://github.com/[YOUR_REPO]/juris_full_project.git
cd juris_full_project
```

### Step 2: Start Backend (Docker)
```bash
docker-compose up -d
```

This single command:
- ✅ Pulls CUDA runtime (1.3GB, one-time)
- ✅ Installs Python + PyTorch (2.2GB, cached after first build)
- ✅ Starts backend on `http://localhost:8000`
- ✅ Starts PostgreSQL database
- ✅ Starts Redis cache

**Verify backend is running:**
```bash
curl http://localhost:8000/
```

Expected response:
```json
{"message": "JurisGuardRAG API", "status": "running"}
```

### Step 3: Start Frontend (Node)
```bash
cd frontend
npm install  # First time only
npm run dev
```

Frontend runs on `http://localhost:5173`

### Step 4: Upload Your First Document
1. Open `http://localhost:5173` in browser
2. Click **Upload**
3. Select a PDF (sample: `tester.pdf`)
4. Click **Upload**

### Step 5: Run System Evaluation
1. Click **Diagnostics**
2. Click **▶️ Run Full System Evaluation**
3. See 10/10 tests pass! ✅

---

## 🔍 Detailed Backend Setup (If Not Using Docker)

### Option A: Docker (Recommended)
```bash
# One command, everything works
docker-compose up -d
```

**Check logs:**
```bash
docker-compose logs -f backend
```

**Stop everything:**
```bash
docker-compose down
```

### Option B: Local Python Setup
If you prefer running without Docker:

```bash
# 1. Create Python environment (requires Python 3.10+)
python3.10 -m venv venv
source venv/bin/activate

# 2. Install dependencies
cd backend
pip install -r requirements.txt

# 3. Download models
bash scripts/download_models.sh

# 4. Start backend
cd src
uvicorn main:app --host 0.0.0.0 --port 8000 --reload
```

---

## 🎨 Frontend Setup Details

### First-Time Setup
```bash
cd frontend
npm install
npm run build  # Production build
npm run preview  # Test production build
```

### Development Mode
```bash
npm run dev  # Hot reload on port 5173
```

### Production Build
```bash
npm run build  # Creates `dist/` folder
npm run preview  # Serves production build locally
```

---

## 🔧 Configuration

### Backend Configuration
Edit `backend/config/config.yaml` to customize:

```yaml
models:
  load_in_4bit: true        # 4-bit quantization (requires CUDA)
  max_seq_length: 2048      # LLM context length

ingestion:
  chunk_size: 500           # Document chunk size (characters)
  chunk_overlap: 150        # Overlap between chunks (prevents missed info)

security:
  similarity_threshold: 0.35  # Semantic similarity cutoff for retrieval
  sentinel_threshold: 0.85    # Sensitivity detection threshold
```

### Environment Variables
Create `backend/.env`:
```env
DATABASE_URL=postgresql://admin:admin123@localhost:5432/juris_db
REDIS_URL=redis://localhost:6379/0
HF_HUB_OFFLINE=1
```

---

## 🧪 Testing & Evaluation

### Run Full Evaluation Suite
```bash
curl -X POST http://localhost:8000/evaluate | jq .
```

### View Last Evaluation Results (with details)
```bash
curl http://localhost:8000/debug/evaluation | jq .
```

### See All Document Chunks
```bash
curl http://localhost:8000/debug/metadata | jq '.chunks | length'
```

### Test Semantic Search
```bash
curl "http://localhost:8000/debug/semantic?query=notice%20period&threshold=0.3"
```

---

## 🗑️ Complete Fresh Start

**Reset everything** (deletes ingested documents, keeps code):
```bash
docker-compose down
sudo rm -rf backend/data/juris_faiss_db
docker-compose up -d
```

**Hard reset** (full cleanup):
```bash
docker-compose down -v
docker system prune -a
sudo rm -rf backend/data
docker-compose up -d --build
```

---

## 📊 Project Structure

```
juris_full_project/
├── backend/
│   ├── src/
│   │   ├── api.py           # FastAPI endpoints
│   │   ├── models.py        # LLM + embeddings
│   │   ├── security.py      # RBAC + sensitivity detection
│   │   ├── ingestion.py     # PDF processing + chunking
│   │   └── query.py         # RAG retrieval logic
│   ├── config/
│   │   └── config.yaml      # All tunable settings
│   ├── data/
│   │   └── juris_faiss_db/  # Vector store (auto-created)
│   ├── Dockerfile
│   └── requirements.txt
│
├── frontend/
│   ├── src/
│   │   ├── pages/
│   │   │   ├── Chat.jsx
│   │   │   ├── Diagnostics.jsx
│   │   │   └── ...
│   │   ├── components/
│   │   └── lib/
│   ├── package.json
│   ├── vite.config.js
│   └── tailwind.config.js
│
├── docker-compose.yml       # Services: backend, postgres, redis
└── README.md
```

---

## 🚨 Troubleshooting

### "Docker command not found"
```bash
# Check Docker is installed and running
docker --version
sudo usermod -aG docker $USER  # Add user to docker group
newgrp docker  # Refresh group
```

### "Port 8000 already in use"
```bash
# Kill process on port 8000
sudo lsof -ti:8000 | xargs kill -9
# Or use different port
docker-compose run -p 9000:8000 backend
```

### "CUDA Setup failed" (GPU issues)
```bash
# Check NVIDIA drivers
nvidia-smi

# If no output, Docker will fall back to CPU (slower but works)
# To use GPU, update docker-compose.yml:
# services:
#   backend:
#     deploy:
#       resources:
#         reservations:
#           devices:
#             - driver: nvidia
#               count: 1
#               capabilities: [gpu]
```

### "PDF Upload Fails"
1. Check backend logs: `docker-compose logs backend`
2. Verify file size < 100MB
3. Ensure PDF is readable (try opening in a PDF reader first)

### "Tests Failing"
```bash
# Clear vector database and re-ingest
docker-compose down
sudo rm -rf backend/data/juris_faiss_db
docker-compose up -d
# Re-upload PDF through UI
```

---

## 📖 API Endpoints (Backend)

| Endpoint | Method | Purpose |
|----------|--------|---------|
| `/` | GET | Health check |
| `/upload` | POST | Upload PDF |
| `/query` | POST | Ask question (with RBAC) |
| `/evaluate` | POST | Run test suite |
| `/debug/metadata` | GET | View all chunks |
| `/debug/semantic?query=X` | GET | Test retrieval |
| `/debug/evaluation` | GET | View last eval results |

**Example Query:**
```bash
curl -X POST http://localhost:8000/query \
  -H "Content-Type: application/json" \
  -d '{
    "query": "What is the notice period?",
    "role": "guest"
  }'
```

---

## 🔑 Key Features

✅ **Semantic RAG** - Smart document retrieval using embeddings  
✅ **Role-Based Access Control** - Admin vs Guest access levels  
✅ **Sensitivity Detection** - Prevents leaking confidential info  
✅ **4-Bit Quantization** - Efficient LLM inference on consumer GPU  
✅ **Vector Database** - FAISS for fast similarity search  
✅ **Automated Testing** - 10-test evaluation suite  
✅ **Clean Docker Setup** - No local dependency hell  

---

## 🤝 Contributing

1. Create a branch: `git checkout -b feature/your-feature`
2. Make changes
3. Test locally: `docker-compose up && npm run dev`
4. Commit: `git commit -m "Add feature"`
5. Push: `git push origin feature/your-feature`

---

## 📝 License

[Your License Here]

---

## 🆘 Support

**Need help?**
- Check [TECHNICAL_REFERENCE.md](TECHNICAL_REFERENCE.md) for architecture details
- Review [IMPLEMENTATION_SUMMARY.md](IMPLEMENTATION_SUMMARY.md) for component overview
- See logs: `docker-compose logs -f backend`

---

**Last Updated:** January 17, 2026  
**Status:** ✅ Production Ready

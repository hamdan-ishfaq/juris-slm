# JurisGuard V2

On-premise, air-gap capable legal intelligence platform.

## Phase 0 — Asset download (you run this locally)

### 1. Setup Python env (once)

```bash
cd v2
python3 -m venv .venv
source .venv/bin/activate          # Windows WSL / Linux
pip install -r scripts/requirements-download.txt
```

Optional — faster HF downloads (token stays local, never committed):

```bash
cp .env.example .env
# Edit .env and set: HF_TOKEN=hf_your_token_here
# Create token at: https://huggingface.co/settings/tokens
```

### 2. See what will be downloaded

```bash
python scripts/download_assets.py --list
```

### 3. Download everything (datasets + models)

```bash
python scripts/download_assets.py --all
```

Progress shows **file name**, **downloaded / total**, **speed**, and **ETA** for each file.

### 4. Download selectively

```bash
# One dataset (good for testing)
python scripts/download_assets.py --datasets --only cuad

# Models only (embeddings + reranker + Ollama phi3.5)
python scripts/download_assets.py --models

# Single model
python scripts/download_assets.py --models --only bge-m3
```

### Overnight model download (remaining models)

**Disable laptop sleep first** (plugged in → sleep: Never).

```bash
cd v2
nohup python scripts/download_overnight.py > data/nohup.out 2>&1 &
echo "PID: $!"
tail -f data/download_overnight.log
```

In the morning: `python scripts/verify_assets.py`

```bash
python scripts/verify_assets.py
# or: bash scripts/00_verify_datasets.sh
```

### Storage layout

| Asset | Path |
|-------|------|
| CUAD, LEDGAR, ContractNLI, MAUD | `data/raw/<name>/` |
| BGB, GDPR law texts | `data/raw/law_corpus/*.txt` |
| bge-m3 embeddings | `data/models/bge-m3/` |
| Cross-encoder reranker | `data/models/reranker/` |
| Phi-3.5-mini (Ollama) | Ollama model store (`ollama list`) |

### Ollama note

`phi35-ollama` runs `ollama pull phi3.5`. Requires Ollama installed and running:

```bash
# Option A: native
curl -fsSL https://ollama.com/install.sh | sh
ollama serve   # if not already running

# Option B: Docker (Phase 2 docker-compose)
docker compose up ollama -d
```

### Estimated total download size

| Category | Size |
|----------|------|
| All datasets | ~8–12 GB |
| bge-m3 + reranker | ~1.2 GB |
| phi3.5 via Ollama | ~2.3 GB |
| **Total** | **~12–16 GB** |

---

## Quick start (Phase 0.1)

```bash
cd v2
chmod +x scripts/*.sh
bash scripts/00_verify_gpu.sh
```

---

## Phase 1 — Training data preparation (you run these)

All commands show **tqdm progress bars**. Run from `v2/` with venv active.

### Step 1 — Convert each dataset to instruction JSONL (one command at a time)

```bash
cd ~/juris_full_project/v2
source .venv/bin/activate

python scripts/02_prepare_training_data.py --only cuad
python scripts/02_prepare_training_data.py --only contract_nli
python scripts/02_prepare_training_data.py --only ledgar
python scripts/02_prepare_training_data.py --only maud
```

Or all at once (~2–5 min total):

```bash
python scripts/02_prepare_training_data.py --all
```

Verify Step 1:

```bash
python scripts/verify_training_data.py
```

Expect 4 OK under Phase 1.1 (final splits still missing).

### Step 2 — Merge into train/eval splits for Colab

```bash
python scripts/04_build_final_dataset.py
python scripts/verify_training_data.py
```

Expect **Phase 1 COMPLETE** with ~80k–100k+ train examples (depends on dedup).

Output files to upload to Google Drive for Colab fine-tuning:

- `data/processed/train_final.jsonl`
- `data/processed/eval_set.jsonl`

### Step 3 — OPTIONAL synthetic data (skip for now — needs Ollama)

```bash
# Only after: ollama pull phi3.5
python scripts/03_generate_synthetic.py --max-examples 100   # quick test
python scripts/04_build_final_dataset.py                     # re-merge
```

| Phase | Script | Status |
|-------|--------|--------|
| 1.1 Prepare pairs | `02_prepare_training_data.py` | — |
| 1.2 Merge splits | `04_build_final_dataset.py` | — |
| 1.3 Synthetic (optional) | `03_generate_synthetic.py` | — |
| 1 Verify | `verify_training_data.py` | — |

---

## Phase 1.3 — Local smoke test (run before Colab)

Confirms GPU, data formatting, checkpoint save, and **full resume** on your RTX 4050.

**Stop any run downloading ~7.6 GB** — the script now uses pre-quantized 4-bit weights (~2.3 GB).

```bash
cd ~/juris_full_project/v2
source .venv/bin/activate
pip install -r scripts/requirements-finetune.txt

# Standard path (~2.3 GB model download, no flash-attn needed)
python scripts/05_smoke_test_finetune.py

# Optional — Unsloth (faster training; Colab uses this too)
pip install -r scripts/requirements-finetune-unsloth.txt
python scripts/05_smoke_test_finetune.py --use-unsloth

# Test resume (after smoke test completes)
python scripts/05_smoke_test_finetune.py --resume --max-steps 50
```

| Topic | Recommendation |
|-------|----------------|
| **Flash-attention** | Skip on WSL (hard to compile). `eager` is fine for 400 examples. Colab Unsloth enables fast kernels automatically. |
| **Unsloth locally** | Optional speed boost. **Required on Colab** for full 94k training. |
| **HF token** | Set `HF_TOKEN` in `v2/.env` for faster downloads |

What it checks:
- 400 examples, 30 steps, saves every 10 steps
- Full checkpoint copied to `data/smoke_checkpoints/checkpoint_RESUME/`
- Final LoRA adapter in `data/smoke_checkpoints/final_adapter/`

---

## Phase 1.4 — Colab fine-tune (crash-safe, resume from Drive)

### 1. Upload to Google Drive

```
My Drive/JurisGuard/training/
  train_final.jsonl
  eval_set.jsonl
```

### 2. Open notebook

Upload or open `v2/notebooks/phi35_legal_finetune.ipynb` in Colab.

Runtime → **T4 GPU** → Run all cells.

### 3. Crash recovery (even days later)

Training writes to Drive:
- `checkpoints/checkpoint-*` — rolling saves (last 5)
- `checkpoint_RESUME/` — **always the latest full state** (model + optimizer + scheduler + RNG)
- `RUN_MANIFEST.json` — last step, status, recent loss
- `tokenized_cache/` — skip re-tokenizing 94k examples on resume

If Colab disconnects: re-open notebook → **Run all** → cell 7 auto-resumes from `checkpoint_RESUME/`.

**Do not delete `checkpoint_RESUME/` until training completes.**

### 4. After training

Download GGUF from `My Drive/JurisGuard/training/gguf/` and import locally with Ollama.

---

## Phase 2 — Runtime stack (build now while fine-tune paused)

Fine-tune resumes on Colab later; **app development uses base `phi3.5`** until GGUF is ready.

See **`docs/TRAINING_CHECKPOINTS.md`** for your local copy at:
`C:\Users\mhamd\Desktop\PROJECT\juris\training`

### Setup

```bash
cd ~/juris_full_project/v2
cp .env.example .env
# Edit TRAINING_DIR if your training folder path differs

docker compose up -d --build
docker compose exec ollama ollama pull phi3.5
```

### Run migrations

```bash
docker compose exec api alembic upgrade head
```

### Verify

```bash
bash scripts/00_verify_phase2.sh
curl http://localhost:8002/api/v1/status
```

| Service | URL | Notes |
|---------|-----|-------|
| API | http://localhost:8002 | v2 backend |
| API docs | http://localhost:8002/docs | OpenAPI |
| Ollama | http://localhost:11434 | LLM |
| Postgres | localhost:5433 | pgvector |
| Redis | localhost:6380 | Celery queue (Phase 3) |

Ports **5433 / 6380 / 8002** avoid clashes with v1 stack.

### Model swap (when training finishes)

1. Export GGUF in Colab (Cell 8) → copy to `training/gguf/`
2. `ollama create jurisguard-v1 -f deploy/Modelfile.example`
3. Change `.env`: `OLLAMA_MODEL=jurisguard-v1`
4. `docker compose restart api`

| Phase | Scope | Status |
|-------|--------|--------|
| 2.1 | Docker + pgvector + API scaffold | done |
| 2.2 | Auth (JWT register/login) | done |
| 2.3 | Law corpus → pgvector | done (run ingest) |
| 3 | RAG + chat (bge-m3, reranker, Ollama) | done (basic) |
| 4 | Matters, audit, comparison | planned |
| 5 | Frontend polish | planned |

---

## Phase 2.2–3 — Auth, law corpus, RAG chat

### 1. Rebuild API (layered Docker — CPU torch ~200MB, not 500MB CUDA)

```bash
cd ~/juris_full_project/v2
grep -q AUTH_SECRET_KEY .env || echo 'AUTH_SECRET_KEY=dev-secret-change-in-prod' >> .env
docker compose build api    # first build ~5–10 min; code-only edits reuse cache
docker compose up -d api
```

Docker layers: `requirements-base` → `torch (cpu)` → `requirements-ml` → `src/`.  
Editing Python under `backend/src/` does **not** re-download PyTorch.

### 2. Download law texts + models (if missing)

```bash
source .venv/bin/activate
python scripts/download_assets.py --datasets --only gdpr
python scripts/download_assets.py --datasets --only bgb
python scripts/download_assets.py --models --only bge-m3
python scripts/download_assets.py --models --only reranker
```

### 3. Fix shell scripts (Windows CRLF → WSL errors on `set -euo pipefail`)

```bash
python scripts/fix_sh_crlf.py
# or: sed -i 's/\r$//' scripts/*.sh
```

### 4. Verify bge-m3 weights (must be ≥500MB, not just config JSON)

```bash
python scripts/verify_assets.py
# if bge-m3 missing weights:
python scripts/download_assets.py --models --only bge-m3
```

### 5. Ingest law corpus into pgvector (~5–15 min CPU)

**Recommended (host venv, no Docker rebuild):**

```bash
source .venv/bin/activate
pip install -r backend/requirements-base.txt
pip install "torch==2.5.1" --index-url https://download.pytorch.org/whl/cpu
pip install -r backend/requirements-ml.txt
python scripts/run_ingest_law.py
curl -s http://localhost:8002/api/v1/corpus/stats | python3 -m json.tool
```

Or after fixing CRLF: `bash scripts/ingest_law_host.sh`

**Docker ingest** (only if API image already built with `requirements-ml.txt` pins):

```bash
docker compose exec api python /app/src/ingest_law.py
```

`backend/src` is volume-mounted — embedding loader fixes apply without rebuilding.

### 6. Test auth + RAG chat

```bash
python scripts/00_verify_phase23.py
# or: bash scripts/00_verify_phase23.sh
```

### Docker build failures (hash / network)

If `pip install` fails with **hash mismatch** or **No address associated with hostname**, retry when the network is stable — do **not** use `--no-cache` unless necessary. Pin `pydantic-core` in `requirements-base.txt` reduces hash drift. If an older API image already works, skip rebuild and use host ingest above.

Or manually:

```bash
# Register
curl -s -X POST http://localhost:8002/api/v1/auth/register \
  -H "Content-Type: application/json" \
  -d '{"email":"you@example.com","password":"yourpass123"}'

# Chat (use token from register)
curl -s -X POST http://localhost:8002/api/v1/chat \
  -H "Authorization: Bearer YOUR_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"message":"What does GDPR say about consent?","use_law_corpus":true}'
```

API docs: http://localhost:8002/docs

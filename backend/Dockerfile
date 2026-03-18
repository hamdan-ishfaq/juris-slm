FROM nvidia/cuda:12.1.1-runtime-ubuntu22.04

RUN apt-get update && apt-get install -y \
    python3.10 \
    python3-pip \
    build-essential \
    libpq-dev \
    curl \
    && rm -rf /var/lib/apt/lists/*

RUN ln -s /usr/bin/python3.10 /usr/bin/python

WORKDIR /app

# ── Layer 1: PyTorch + CUDA (heaviest, ~3 GB, almost never changes) ────────
RUN pip install --no-cache-dir \
    --default-timeout=1000 \
    --retries 5 \
    --extra-index-url https://download.pytorch.org/whl/cu121 \
    torch==2.1.2+cu121 \
    torchaudio==2.1.2+cu121 \
    torchvision==0.16.2+cu121

# ── Layer 2: Heavy ML deps (~500 MB, changes only when model stack changes) ─
COPY requirements-heavy.txt .
RUN pip install --no-cache-dir \
    --default-timeout=1000 \
    --retries 5 \
    -r requirements-heavy.txt

# ── Layer 3: Light app deps (~50 MB, changes when you add a new package) ───
COPY requirements.txt .
RUN pip install --no-cache-dir \
    --default-timeout=1000 \
    --retries 5 \
    -r requirements.txt

# ── Layer 4: Model warmup (optional) ──────────────────────────────────────
ARG WARMUP_MODELS=false
RUN if [ "$WARMUP_MODELS" = "true" ]; then \
        python -c "from transformers import pipeline; pipeline('zero-shot-classification', model='facebook/bart-large-mnli')"; \
    else \
        echo "Skipping model warmup (set WARMUP_MODELS=true to pre-download)"; \
    fi

# ── Layer 5: Application code (changes constantly — always last) ───────────
COPY . .

EXPOSE 8000
CMD ["uvicorn", "src.main:app", "--host", "0.0.0.0", "--port", "8000"]

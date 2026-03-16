FROM nvidia/cuda:12.1.1-runtime-ubuntu22.04

# Install Python and system dependencies
RUN apt-get update && apt-get install -y \
    python3.10 \
    python3-pip \
    build-essential \
    libpq-dev \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Symlink python3 to python
RUN ln -s /usr/bin/python3.10 /usr/bin/python

# Set working directory
WORKDIR /app

# ============================================================================
# LAYER 1: HEAVY DEPENDENCIES (Cached permanently unless versions change)
# ============================================================================
# Install PyTorch separately BEFORE copying requirements.txt
# This layer will persist even if requirements.txt changes
RUN pip install --no-cache-dir \
    --default-timeout=1000 \
    --retries 5 \
    --extra-index-url https://download.pytorch.org/whl/cu121 \
    torch==2.1.2+cu121 \
    torchaudio==2.1.2+cu121 \
    torchvision==0.16.2+cu121

# ============================================================================
# LAYER 2: APPLICATION DEPENDENCIES
# ============================================================================
# Install all Python packages from requirements.txt
COPY requirements.txt .
RUN pip install --no-cache-dir \
    --default-timeout=1000 \
    --retries 5 \
    -r requirements.txt

# ============================================================================
# LAYER 4: MODEL WARMUP (Optional - set WARMUP_MODELS=true to enable)
# ============================================================================
ARG WARMUP_MODELS=false
RUN if [ "$WARMUP_MODELS" = "true" ]; then \
            python -c "from transformers import pipeline; pipeline('zero-shot-classification', model='facebook/bart-large-mnli')"; \
        else \
            echo "Skipping model warmup (set WARMUP_MODELS=true to pre-download)"; \
        fi

# ============================================================================
# LAYER 5: APPLICATION CODE (Changes frequently during development)
# ============================================================================
COPY . .

EXPOSE 8000
CMD ["uvicorn", "src.main:app", "--host", "0.0.0.0", "--port", "8000"]

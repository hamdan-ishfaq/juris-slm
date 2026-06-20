# Layer order = cache-friendly. Only re-downloads when the file ABOVE changes.
FROM python:3.12-slim-bookworm

WORKDIR /app

ENV PIP_DEFAULT_TIMEOUT=600 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

# Layer A — system packages (almost never changes)
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    gosu \
    tesseract-ocr \
    tesseract-ocr-deu \
    poppler-utils \
    && rm -rf /var/lib/apt/lists/*

# Layer B — API deps (~30MB, cached until requirements-base.txt changes)
COPY requirements-base.txt requirements-ml.txt ./
RUN pip install --no-cache-dir -r requirements-base.txt

# Layer C — CPU-only PyTorch (~200MB, NOT 500MB+ CUDA stack)
ARG TORCH_CPU_VERSION=2.6.0
RUN for attempt in 1 2 3; do \
      pip install --no-cache-dir "torch==${TORCH_CPU_VERSION}" \
        --index-url https://download.pytorch.org/whl/cpu \
      && break; \
      echo "torch download failed (attempt ${attempt}), retrying..."; \
      sleep 15; \
    done

# Layer D — sentence-transformers (cached until requirements-ml.txt changes)
RUN pip install --no-cache-dir -r requirements-ml.txt

# Layer E — app code (rebuilds on code edits, does NOT re-run pip above)
COPY alembic.ini .
COPY alembic ./alembic
COPY src ./src
COPY docker-entrypoint.sh /docker-entrypoint.sh

RUN useradd -m -u 1000 -s /bin/bash juris && \
    mkdir -p /app/src/data/uploads /home/juris/.cache/huggingface && \
    chmod +x /docker-entrypoint.sh && \
    chown -R juris:juris /app /home/juris

ENV PYTHONPATH=/app/src \
    HF_HOME=/home/juris/.cache/huggingface \
    TRANSFORMERS_CACHE=/home/juris/.cache/huggingface

ENTRYPOINT ["/docker-entrypoint.sh"]
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000", "--app-dir", "/app/src"]

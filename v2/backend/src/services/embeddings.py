from __future__ import annotations

import threading
from pathlib import Path
from typing import TYPE_CHECKING

import numpy as np

from config import settings

if TYPE_CHECKING:
    from sentence_transformers import SentenceTransformer

_lock = threading.Lock()
_model: SentenceTransformer | None = None


def _embedding_candidates() -> list[str]:
    local = Path(settings.embedding_model_path)
    out: list[str] = []
    if local.is_dir():
        out.append(str(local))
        for sub in local.iterdir():
            if sub.is_dir() and (
                list(sub.glob("*.safetensors")) or list(sub.glob("pytorch_model.bin"))
            ):
                out.append(str(sub))
    out.append("BAAI/bge-m3")
    return out


def get_embedding_model() -> SentenceTransformer:
    global _model
    if _model is not None:
        return _model
    with _lock:
        if _model is not None:
            return _model
        from sentence_transformers import SentenceTransformer

        last_err: Exception | None = None
        for path in _embedding_candidates():
            try:
                _model = SentenceTransformer(path, device="cuda", trust_remote_code=True)
                print(f"Loaded embeddings from: {path}")
                return _model
            except Exception as exc:
                last_err = exc
                print(f"Embedding load failed for {path}: {exc}")
        raise RuntimeError(f"Cannot load embedding model. Last error: {last_err}")


def embed_texts(texts: list[str], batch_size: int = 16) -> np.ndarray:
    if not texts:
        return np.zeros((0, settings.embedding_dim), dtype=np.float32)
    model = get_embedding_model()
    vectors = model.encode(
        texts,
        batch_size=batch_size,
        normalize_embeddings=True,
        show_progress_bar=len(texts) > 50,
    )
    return np.asarray(vectors, dtype=np.float32)

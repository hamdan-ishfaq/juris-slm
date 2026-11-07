from __future__ import annotations

import threading
from pathlib import Path
from typing import TYPE_CHECKING

import numpy as np

from config import settings
from services.ml_device import resolve_device

if TYPE_CHECKING:
    from sentence_transformers import SentenceTransformer

_lock = threading.Lock()
_model: SentenceTransformer | None = None


def _has_model_weights(path: Path) -> bool:
    if not path.is_dir():
        return False
    if (path / "config.json").is_file():
        return True
    return bool(list(path.rglob("*.safetensors")) or list(path.rglob("pytorch_model.bin")))


def _embedding_candidates() -> list[str]:
    local = Path(settings.embedding_model_path)
    out: list[str] = []
    if _has_model_weights(local):
        out.append(str(local))
        for sub in local.iterdir():
            if sub.is_dir() and _has_model_weights(sub):
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

        device = resolve_device(settings.embedding_device)
        last_err: Exception | None = None
        for path in _embedding_candidates():
            try:
                _model = SentenceTransformer(path, device=device, trust_remote_code=True)
                print(f"Loaded embeddings from: {path} device={device}")
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

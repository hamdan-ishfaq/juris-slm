from __future__ import annotations

import threading
from typing import TYPE_CHECKING

from config import settings
from services.ml_device import resolve_device

if TYPE_CHECKING:
    from sentence_transformers import CrossEncoder

_lock = threading.Lock()
_model: CrossEncoder | None = None


def get_reranker() -> CrossEncoder:
    global _model
    if _model is not None:
        return _model
    with _lock:
        if _model is not None:
            return _model
        from pathlib import Path

        from sentence_transformers import CrossEncoder

        local = Path(settings.reranker_model_path)
        candidates: list[str] = []
        if local.is_dir() and (
            (local / "config.json").is_file()
            or list(local.rglob("*.safetensors"))
            or list(local.rglob("pytorch_model.bin"))
        ):
            candidates.append(str(local))
        candidates.append("cross-encoder/ms-marco-MiniLM-L-6-v2")
        device = resolve_device(settings.reranker_device)
        last_err: Exception | None = None
        for path in candidates:
            try:
                _model = CrossEncoder(path, device=device)
                print(f"Loaded reranker from: {path} device={device}")
                return _model
            except Exception as exc:
                last_err = exc
                print(f"Reranker load failed for {path}: {exc}")
        raise RuntimeError(f"Cannot load reranker. Last error: {last_err}")


def rerank(query: str, hits: list[dict], top_k: int | None = None) -> list[dict]:
    if not hits:
        return []
    k = top_k or settings.rag_rerank_k
    model = get_reranker()
    pairs = [(query, h["content"]) for h in hits]
    scores = model.predict(pairs)
    ranked = sorted(zip(hits, scores), key=lambda x: float(x[1]), reverse=True)
    out = []
    for hit, score in ranked[:k]:
        hit = dict(hit)
        hit["rerank_score"] = float(score)
        out.append(hit)
    return out

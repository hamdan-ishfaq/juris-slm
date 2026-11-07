"""ML device selection for embeddings and reranker — Phase 10A."""
from __future__ import annotations

from config import settings

def resolve_device(preference: str) -> str:
    """Resolve device from auto|cuda|cpu."""
    pref = (preference or "auto").strip().lower()
    if pref == "cpu":
        return "cpu"
    try:
        import torch

        cuda_ok = torch.cuda.is_available()
    except Exception:
        cuda_ok = False
    if pref == "cuda":
        return "cuda" if cuda_ok else "cpu"
    return "cuda" if cuda_ok else "cpu"


def cuda_available() -> bool:
    try:
        import torch

        return bool(torch.cuda.is_available())
    except Exception:
        return False


def device_status() -> dict[str, str | bool]:
    """Runtime ML device info for status/health endpoints."""
    resolved_embed = resolve_device(settings.embedding_device)
    resolved_rerank = resolve_device(settings.reranker_device)
    return {
        "cuda_available": cuda_available(),
        "embedding_device_config": settings.embedding_device,
        "reranker_device_config": settings.reranker_device,
        "embedding_device": resolved_embed,
        "reranker_device": resolved_rerank,
        "airgap_latency_profile": settings.is_airgap_latency_profile,
    }

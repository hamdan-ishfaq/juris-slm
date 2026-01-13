# sentinel.py
# "Sentinel" classifier helper for nuanced sensitivity detection (Layer 2).
# Tries to use transformers zero-shot pipeline; if not available falls back to simple keyword heuristic.

from typing import Dict, Any
SENTINEL_KEYWORDS = [
    "confidential", "proprietary", "trade secret", "strategy", "merger", "acquisition", "internal use only",
    "do not share", "sensitive", "secret", "Project Chimera"
]

_pipeline = None
_pipeline_loaded = False

def _try_load_pipeline():
    global _pipeline, _pipeline_loaded
    if _pipeline_loaded:
        return
    _pipeline_loaded = True
    try:
        from transformers import pipeline
        # Using an MNLI model for zero-shot classification. If this downloads a model, it's okay but optional.
        _pipeline = pipeline("zero-shot-classification", model="facebook/bart-large-mnli")
    except Exception:
        _pipeline = None

def classify_text(text: str) -> Dict[str, Any]:
    """
    Returns:
      {"sensitive": bool, "label": str, "score": float, "method": "zeroshot"|"heuristic"}
    """
    if not text:
        return {"sensitive": False, "label": "empty", "score": 0.0, "method": "none"}

    # try transformer zero-shot first (lazy)
    _try_load_pipeline()
    if _pipeline:
        try:
            labels = ["sensitive", "non-sensitive"]
            res = _pipeline(text, labels, multi_class=False)
            label = res["labels"][0]
            score = float(res["scores"][0])
            return {"sensitive": label == "sensitive", "label": label, "score": score, "method": "zeroshot"}
        except Exception:
            # fall through to heuristic
            pass

    # Fallback: keyword heuristic
    low = text.lower()
    hits = [kw for kw in SENTINEL_KEYWORDS if kw.lower() in low]
    if hits:
        # return the fraction of keywords found as a pseudo-score
        score = min(1.0, len(hits) / max(1, len(SENTINEL_KEYWORDS)))
        return {"sensitive": True, "label": "heuristic", "score": score, "method": "heuristic", "hits": hits}
    return {"sensitive": False, "label": "heuristic_non_sensitive", "score": 0.0, "method": "heuristic"}

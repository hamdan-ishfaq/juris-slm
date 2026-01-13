# security.py
"""
Layered security helpers for GuardRAG:
- Layer1: hard filters (regex)
- Layer2: sentinel classifier (optional transformers zero-shot or fallback heuristics)
- Helpers to tag chunks during ingestion
"""

import re
from typing import List, Tuple, Optional

# Hard-coded patterns (easy to extend). These are deterministic "must-block" patterns.
HARD_PATTERNS = [
    r"\bProject Chimera\b",
    r"\bProject\s+Chimera\b",
    r"\bSSN\b",
    r"\bSocial Security Number\b",
    r"\b\d{3}-\d{2}-\d{4}\b",  # US-style SSN
    r"\b4[0-9]{12}(?:[0-9]{3})?\b",  # Visa-like CC (simple)
    r"\b5[1-5][0-9]{14}\b",  # MasterCard-like (simple)
    # add more patterns here
]

_COMPILED_HARD = [re.compile(pat, flags=re.IGNORECASE) for pat in HARD_PATTERNS]

# Heuristic keywords for fallback classifier
SENSITIVE_KEYWORDS = [
    "confidential", "proprietary", "internal only", "do not distribute",
    "trade secret", "strategic plan", "financial forecast", "merger", "acquisition",
]
PUBLIC_KEYWORDS = [
    "public", "published", "press release", "policy", "terms and conditions",
]

# Optional: initialize transformers zero-shot classifier only if available.
try:
    from transformers import pipeline
    _ZSC_PIPE = pipeline("zero-shot-classification", model="facebook/bart-large-mnli")
except Exception:
    _ZSC_PIPE = None


def check_hard_filter(text: str) -> Optional[str]:
    """
    Return the matched pattern name (string) if any hard pattern matches, otherwise None.
    """
    for rx in _COMPILED_HARD:
        if rx.search(text):
            return rx.pattern
    return None


def classify_chunk(text: str) -> str:
    """
    Return sensitivity label: "secret", "sensitive", or "public".
    Uses zero-shot classification if available, otherwise heuristic rules.
    """
    # 1) Hard filter -> secret
    if check_hard_filter(text):
        return "secret"

    # 2) If zero-shot available, use it (fast enough for small chunks)
    if _ZSC_PIPE is not None:
        try:
            candidate_labels = ["public", "sensitive", "secret"]
            result = _ZSC_PIPE(text, candidate_labels, multi_class=False)
            if "labels" in result and len(result["labels"]) > 0:
                label = result["labels"][0].lower()
                # map potential label variants
                if "secret" in label:
                    return "secret"
                if "sensitive" in label:
                    return "sensitive"
                return "public"
        except Exception:
            # fall through to heuristic
            pass

    # 3) Fallback heuristic: presence of sensitive keywords
    txt = text.lower()
    sens_hits = sum(1 for k in SENSITIVE_KEYWORDS if k in txt)
    pub_hits = sum(1 for k in PUBLIC_KEYWORDS if k in txt)

    if sens_hits >= 1 and sens_hits > pub_hits:
        return "sensitive"
    if pub_hits >= 1 and pub_hits >= sens_hits:
        return "public"

    # Default: sensitive (conservative) — better to hide than leak
    return "sensitive"


def tag_chunks(chunks: List[str]) -> List[str]:
    """
    For a list of text chunks, return a parallel list of roles:
      - 'admin' for secret
      - 'sensitive' for limited
      - 'public' for public
    This function is used during ingestion to populate metadata['role'].
    """
    roles = []
    for c in chunks:
        label = classify_chunk(c)
        if label == "secret":
            roles.append("admin")
        elif label == "sensitive":
            roles.append("sensitive")
        else:
            roles.append("public")
    return roles

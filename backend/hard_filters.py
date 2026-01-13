# hard_filters.py
import re
from typing import Dict, Any, List

HARD_PATTERNS = [
    (r"\bProject\s+Chimera\b", "project_chimera", re.IGNORECASE),
    (r"\b\d{3}-\d{2}-\d{4}\b", "ssn", 0),
    (r"\b(?:\d[ -]*?){13,16}\b", "credit_card", 0),
    (r"\bconfidential\b", "confidential", re.IGNORECASE),
    (r"\binternal\s+use\s+only\b", "internal", re.IGNORECASE),
    (r"\btrade\s+secret\b", "trade_secret", re.IGNORECASE),
]

def check_text(text: str) -> Dict[str, Any]:
    """
    Check text against hard-coded patterns.
    Returns: {"matched": bool, "matches": [pattern_names]}
    """
    matches = []
    for pattern, name, flags in HARD_PATTERNS:
        try:
            if re.search(pattern, text, flags):
                matches.append(name)
        except Exception:
            continue
    
    return {
        "matched": len(matches) > 0,
        "matches": matches
    }
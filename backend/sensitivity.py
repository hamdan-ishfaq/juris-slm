# sensitivity.py
# Layer 1 (hard filters) + Layer 2 (semantic classifier implemented with SentenceTransformer embeddings)
import re
from typing import List, Dict, Any, Optional
from pathlib import Path
import json
import numpy as np

# default hard filters (you can edit or load from a JSON file later)
_DEFAULT_HARD_FILTERS = [
    {"name": "project_chimera", "pattern": r"project chimera", "flags": re.I, "tag": "project_chimera"},
    {"name": "ssn", "pattern": r"\b\d{3}[- ]?\d{2}[- ]?\d{4}\b", "flags": 0, "tag": "ssn"},
    {"name": "credit_card", "pattern": r"\b(?:\d[ -]*?){13,16}\b", "flags": 0, "tag": "credit_card"}
]

def load_hard_filters(path: Optional[str] = None) -> List[Dict[str, Any]]:
    if path:
        p = Path(path)
        if p.exists():
            try:
                with open(p, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    return data
            except Exception:
                pass
    return _DEFAULT_HARD_FILTERS

def run_hard_filters(text: str, filters: Optional[List[Dict[str,Any]]] = None) -> Dict[str,Any]:
    """
    Return {matched: bool, matches: [names], tags: [tags]}
    """
    if filters is None:
        filters = _DEFAULT_HARD_FILTERS
    matches = []
    tags = []
    for f in filters:
        pat = f.get("pattern")
        flags = f.get("flags", 0)
        name = f.get("name")
        tag = f.get("tag", name)
        try:
            if re.search(pat, text, flags):
                matches.append(name)
                tags.append(tag)
        except re.error:
            # ignore broken regex
            continue
    return {"matched": len(matches) > 0, "matches": matches, "tags": tags}

def semantic_sensitivity_classify(texts, embedder, label_texts=None, threshold=0.55):
    """
    Classify list of texts by semantic similarity to label descriptions using 'embedder'
    embedder: SentenceTransformer instance with .encode([...], convert_to_numpy=True)
    label_texts: dict label->description, e.g. {'sensitive':'...', 'public':'...'}
    returns list of {'label':..., 'score':...}
    """
    if label_texts is None:
        label_texts = {
            "sensitive": "This text contains proprietary, confidential, or sensitive business, financial or legal strategy.",
            "public": "This text is public information, general policy, or non-sensitive guidance."
        }
    labels = list(label_texts.keys())
    descriptions = [label_texts[l] for l in labels]
    # get embeddings (batch)
    try:
        desc_embs = embedder.encode(descriptions, convert_to_numpy=True)
        text_embs = embedder.encode(texts, convert_to_numpy=True)
    except Exception as e:
        # if encoding fails, mark as 'sensitive' to be safe
        return [{"label":"sensitive", "score":1.0} for _ in texts]

    # cosine similarity
    def cos(a,b):
        a = a / np.linalg.norm(a)
        b = b / np.linalg.norm(b)
        return float(np.dot(a,b))

    results = []
    for te in text_embs:
        best_label = None
        best_score = -1.0
        for li, de in enumerate(desc_embs):
            s = cos(te, de)
            if s > best_score:
                best_score = s
                best_label = labels[li]
        # thresholding: if best_score is below threshold, treat as public (or optionally "unknown")
        chosen = best_label if best_score >= threshold else "public"
        results.append({"label": chosen, "score": float(best_score)})
    return results

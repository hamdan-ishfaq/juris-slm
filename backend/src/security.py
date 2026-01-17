# security.py
# src/security.py - Unified security layers for GuardRAG
import re
import logging
from typing import Dict, Any, List, Optional
from abc import ABC, abstractmethod
import torch

try:
    from transformers import pipeline
    HF_AVAILABLE = True
except ImportError:
    HF_AVAILABLE = False

logger = logging.getLogger(__name__)

class SecurityLayer(ABC):
    @abstractmethod
    def check(self, text: str) -> Dict[str, Any]:
        pass

class HardFilter(SecurityLayer):
    def __init__(self, patterns):
        self.patterns = []
        for p in patterns:
            flags = 0
            if p.flags.upper() == "IGNORECASE":
                flags = re.IGNORECASE
            self.patterns.append((re.compile(p.pattern, flags), p.tag))

    def check(self, text: str) -> Dict[str, Any]:
        tags = []
        for pat, tag in self.patterns:
            if pat.search(text):
                tags.append(tag)
        # Determine forced role: if sensitive tags detected, set admin-only
        forced_role = "admin" if any(tag in tags for tag in ["project_chimera", "confidential", "ssn", "credit_card"]) else None
        return {"tags": tags, "forced_role": forced_role}

class SentinelClassifier(SecurityLayer):
    def __init__(self, model_name: str = "facebook/bart-large-mnli", device: Optional[int] = None):
        self.available = False
        self.pipeline = None
        self.model_name = model_name
        self.device = device or (0 if torch.cuda.is_available() else -1)
        if HF_AVAILABLE:
            try:
                self.pipeline = pipeline("zero-shot-classification", model=self.model_name, device=self.device)
                self.available = True
                logger.info(f"Sentinel classifier initialized with {self.model_name}.")
            except Exception as e:
                logger.warning(f"Sentinel failed to initialize: {e}")

    def check(self, text: str, candidate_labels: Optional[List[str]] = None) -> Dict[str, Any]:
        if not self.available or not self.pipeline:
            return {"label": None, "score": 0.0, "method": "none"}
        if candidate_labels is None:
            candidate_labels = ["public", "internal", "confidential", "pii", "financial", "legal"]
        try:
            res = self.pipeline(text, candidate_labels, multi_class=False)
            return {"label": res["labels"][0], "score": float(res["scores"][0]), "method": "zeroshot"}
        except Exception as e:
            logger.warning(f"Sentinel scoring failed: {e}")
            return {"label": None, "score": 0.0, "method": "error"}

class KeywordHeuristic(SecurityLayer):
    def __init__(self, sensitive_keywords: List[str], public_keywords: List[str]):
        self.sensitive_keywords = set(kw.lower() for kw in sensitive_keywords)
        self.public_keywords = set(kw.lower() for kw in public_keywords)

    def check(self, text: str) -> Dict[str, Any]:
        low = text.lower()
        sens_hits = sum(1 for kw in self.sensitive_keywords if kw in low)
        pub_hits = sum(1 for kw in self.public_keywords if kw in low)
        if sens_hits > pub_hits:
            return {"label": "sensitive", "score": min(1.0, sens_hits / len(self.sensitive_keywords)), "method": "heuristic"}
        return {"label": "public", "score": 0.0, "method": "heuristic"}

class SecurityManager:
    def __init__(self, config):
        self.hard_filter = HardFilter(config.security.hard_patterns)
        self.sentinel = SentinelClassifier(config.models.classifier_model)
        self.heuristic = KeywordHeuristic(config.security.sensitive_keywords, config.security.public_keywords)
        self.threshold = config.security.sentinel_threshold

    def assess_chunk(self, text: str) -> Dict[str, Any]:
        # Layer 1: Hard filter
        hf = self.hard_filter.check(text)
        role = hf.get("forced_role", "public")

        # Layer 2: Sentinel or heuristic
        sent = self.sentinel.check(text)
        if sent["method"] == "zeroshot" and sent["score"] >= self.threshold:
            if sent["label"] in ["confidential", "pii", "internal", "financial"]:
                role = "admin"

        # Fallback to heuristic if sentinel failed
        if sent["method"] != "zeroshot":
            heur = self.heuristic.check(text)
            if heur["label"] == "sensitive":
                role = "admin"

        return {
            "role": role or "public",  # Ensure role is never None/null
            "tags": hf["tags"],
            "sentinel_label": sent.get("label"),
            "sentinel_score": sent.get("score", 0.0)
        }

    def check_query(self, text: str) -> Dict[str, Any]:
        hf = self.hard_filter.check(text)
        sent = self.sentinel.check(text)
        return {"hard_filter": hf, "sentinel": sent}
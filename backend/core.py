# core.py
"""
core.py - GuardRAG Logic Layer
Defense-in-Depth:
  Layer 1: Hard filters (regex & keywords) => immediate tagging / forced role
  Layer 2: Sentinel classifier (optional, transformer-based) => nuanced sensitivity
  Layer 3: DB-level enforcement: when answering, we only pass allowed chunks to the LLM
This file is intended to be drop-in compatible with the rest of the Juris project.
"""

import os
import re
import pickle
import logging
from pathlib import Path
from typing import List, Dict, Any, Optional, Tuple
import math
import time

import torch
import numpy as np
import faiss
import pdfplumber

# embedding model (sentence-transformers)
from sentence_transformers import SentenceTransformer

# hf transformers are optional for sentinel (Layer 2)
# we import lazily; failure is handled gracefully
try:
    from transformers import pipeline, AutoTokenizer, AutoModelForSequenceClassification
    HF_AVAILABLE = True
except Exception:
    HF_AVAILABLE = False

# LLM and PEFT
from transformers import AutoModelForCausalLM, AutoTokenizer
from peft import PeftModel

# sklearn helper (cosine similarity)
from sklearn.metrics.pairwise import cosine_similarity

# logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("core")

# ---------------------------
# Utility functions / classes
# ---------------------------

def smart_chunk_text(text: str, chunk_size: int = 500, overlap: int = 50) -> List[str]:
    """
    Break text into chunks of roughly chunk_size chars, prefer sentence boundaries.
    """
    if not text:
        return []
    sentences = re.split(r'(?<=[\.\?\!]\s)', text)  # keep punctuation
    chunks = []
    current = ""
    for s in sentences:
        if len(current) + len(s) <= chunk_size:
            current += s
        else:
            if current:
                chunks.append(current.strip())
            # if sentence is larger than chunk_size, split it
            if len(s) > chunk_size:
                start = 0
                while start < len(s):
                    sub = s[start:start+chunk_size]
                    chunks.append(sub.strip())
                    start += (chunk_size - overlap)
                current = ""
            else:
                current = s
    if current:
        chunks.append(current.strip())
    # ensure overlap between chunks by re-chunking slightly
    if overlap > 0 and len(chunks) > 1:
        merged = []
        for i, c in enumerate(chunks):
            if i == 0:
                merged.append(c)
            else:
                prev = merged[-1]
                # create overlap by appending first overlap chars of current to prev if not already present
                overlap_text = c[:overlap]
                if not prev.endswith(overlap_text):
                    merged[-1] = (prev + " " + overlap_text).strip()
                merged.append(c)
        chunks = merged
    return chunks


class HardFilter:
    """
    Layer 1: Hard rules using regex and keywords.
    Returns a sensitivity tag and a forced role if necessary.
    """
    DEFAULT_PATTERNS = [
        # example PII patterns (simple)
        (re.compile(r'\b\d{3}-\d{2}-\d{4}\b'), 'pii_ssn'),
        (re.compile(r'\b(?:\d[ -]*?){13,16}\b'), 'pii_cc'),  # naive CC pattern
        (re.compile(r'Project\s+Chimera', re.I), 'project_chimera'),
        (re.compile(r'\bconfidential\b', re.I), 'confidential'),
        (re.compile(r'\binternal use only\b', re.I), 'internal'),
        (re.compile(r'\btrade secret\b', re.I), 'trade_secret'),
    ]

    def __init__(self, extra_keywords: Optional[List[str]] = None):
        self.patterns = list(self.DEFAULT_PATTERNS)
        if extra_keywords:
            for kw in extra_keywords:
                self.patterns.append((re.compile(re.escape(kw), re.I), f'keyword_{kw}'))

    def inspect(self, text: str) -> Dict[str, Any]:
        tags = []
        for pat, name in self.patterns:
            if pat.search(text):
                tags.append(name)
        # Determine forced role: if project_chimera or confidential or PII detected, set admin-only
        forced_role = None
        if any(t in tags for t in ('project_chimera', 'confidential', 'pii_ssn', 'pii_cc', 'trade_secret', 'internal')):
            forced_role = 'admin'
        return {"tags": tags, "forced_role": forced_role}


class SentinelClassifier:
    """
    Layer 2: Optional small classifier that decides sensitivity.
    If HF transformers and a model are available, this will instantiate a classifier pipeline.
    Otherwise we provide a 'not available' fallback.
    The classifier is optional and treated as advisory: final decision merges Layer1 and Layer2.
    """
    def __init__(self, model_name: str = "facebook/bart-large-mnli", device: Optional[int] = None):
        self.available = False
        self.pipeline = None
        self.model_name = model_name
        self.device = device
        if not HF_AVAILABLE:
            logger.info("Sentinel: transformers not available, will skip Layer 2 classifier.")
            return
        try:
            dev = 0 if (device is not None and device >= 0 and torch.cuda.is_available()) else -1
            # Using zero-shot-classification pipeline for quick "sensitivity" score
            self.pipeline = pipeline(
                "zero-shot-classification",
                model=self.model_name,
                device=dev
            )
            self.available = True
            logger.info(f"Sentinel classifier initialized with {self.model_name} (device={dev}).")
        except Exception as e:
            logger.warning("Sentinel classifier failed to initialize: %s", e)
            self.available = False

    def score(self, text: str, candidate_labels: Optional[List[str]] = None) -> Dict[str, Any]:
        """
        Returns a dict like {"label_scores": {label:score}, "top_label": label, "top_score": score}.
        If not available, returns empty structure.
        """
        if not self.available or not self.pipeline:
            return {"label_scores": {}, "top_label": None, "top_score": 0.0}
        if candidate_labels is None:
            candidate_labels = ["public", "internal", "confidential", "pii", "financial", "legal"]
        try:
            out = self.pipeline(text, candidate_labels, multi_label=False)
            # pipeline returns {'labels': [...], 'scores': [...], ...}
            label_scores = {lab: float(score) for lab, score in zip(out.get("labels", []), out.get("scores", []))}
            top_label = out.get("labels", [None])[0]
            top_score = float(out.get("scores", [0.0])[0]) if out.get("scores") else 0.0
            return {"label_scores": label_scores, "top_label": top_label, "top_score": top_score}
        except Exception as e:
            logger.warning("Sentinel scoring failed: %s", e)
            return {"label_scores": {}, "top_label": None, "top_score": 0.0}


# ---------------------------
# GuardRAG core engine
# ---------------------------

class GuardRAG:
    """
    Main RAG engine - lazy loads resources.
    Metadata per chunk: {source, role (admin/public), doc_id, tags, sentinel_label, sentinel_score}
    """

    SYSTEM_PROMPT = """<|system|>
You are a skilled legal assistant named Juris.
Use the Context below to answer the user's question.
If the exact answer is not in the text, USE YOUR KNOWLEDGE to draft a reasonable response based on the available facts.
Do NOT say "I cannot answer" unless the context is completely irrelevant.
Be professional, detailed, and helpful.
<|end|>"""

    def __init__(
        self,
        db_folder: str = "./juris_faiss_db",
        model_path: str = "./juris_local_proof",
        embedding_model_name: str = "all-MiniLM-L6-v2",
        max_seq_length: int = 2048,
        load_in_4bit: bool = True,
        top_k: int = 3,
        hard_keywords: Optional[List[str]] = None,
        sentinel_model_name: str = "facebook/bart-large-mnli"
    ):
        self.db_folder = Path(db_folder)
        self.model_path = Path(model_path)
        self.embedding_model_name = embedding_model_name
        self.max_seq_length = max_seq_length
        self.load_in_4bit = load_in_4bit
        self.top_k = top_k

        # Components
        self.embedding_model = None  # SentenceTransformer
        self.llm_tokenizer = None
        self.llm_model = None  # base or peft model
        self.faiss_index = None
        self.metadata: Optional[List[Dict[str, Any]]] = None
        self.documents: Optional[List[str]] = None

        # Layer components
        self.hard_filter = HardFilter(extra_keywords=hard_keywords or [])
        # sentinel is optional and only created if HF available
        self.sentinel = None
        # choose device int for HF if cuda available
        self._hf_device = 0 if torch.cuda.is_available() else -1
        if HF_AVAILABLE:
            try:
                self.sentinel = SentinelClassifier(model_name=sentinel_model_name, device=self._hf_device)
            except Exception:
                self.sentinel = None

        logger.info("GuardRAG Engine initialized (Lazy Loading ON)")

    # ---------------------------
    # Resource loading
    # ---------------------------
    def _load_resources(self):
        """
        Lazy-load embeddings, faiss index, tokenizer, and LLM (base + adapters).
        Safe/noisy operations are logged.
        """
        # 1) Embedding model
        if self.embedding_model is None:
            logger.info("Loading embedding model: %s (CPU)", self.embedding_model_name)
            try:
                # force CPU for embeddings to keep GPU memory for LLM
                self.embedding_model = SentenceTransformer(self.embedding_model_name, device="cpu")
            except Exception as e:
                logger.error("Failed to load embedding model: %s", e)
                raise

        # 2) FAISS DB & metadata
        if self.faiss_index is None or self.metadata is None or self.documents is None:
            logger.info("Loading FAISS DB from %s", str(self.db_folder))
            index_path = self.db_folder / "faiss.index"
            meta_path = self.db_folder / "metadata.pkl"
            if not index_path.exists() or not meta_path.exists():
                raise FileNotFoundError(f"FAISS index or metadata not found in {self.db_folder}")
            try:
                self.faiss_index = faiss.read_index(str(index_path))
                with open(meta_path, "rb") as f:
                    data = pickle.load(f)
                    # expected structure: {"metadata": [...], "documents": [...]}
                    self.metadata = data.get("metadata", [])
                    self.documents = data.get("documents", [])
                logger.info("Loaded faiss index (%d chunks) and metadata.", len(self.documents))
            except Exception as e:
                logger.error("Failed to load FAISS DB / metadata: %s", e)
                raise

        # 3) LLM tokenizer + model (deferred; only load base model when needed)
        if self.llm_model is None or self.llm_tokenizer is None:
            logger.info("Loading LLM tokenizer and model (may be large).")
            # tokenizer from either adapter dir or model id
            try:
                tok_source = str(self.model_path) if (self.model_path / "tokenizer.json").exists() or (self.model_path / "tokenizer_config.json").exists() else "microsoft/Phi-3-mini-4k-instruct"
            except Exception:
                tok_source = "microsoft/Phi-3-mini-4k-instruct"
            try:
                self.llm_tokenizer = AutoTokenizer.from_pretrained(tok_source, trust_remote_code=True)
            except Exception as e:
                logger.warning("Tokenizer load from %s failed: %s. Falling back to hub name.", tok_source, e)
                self.llm_tokenizer = AutoTokenizer.from_pretrained("microsoft/Phi-3-mini-4k-instruct", trust_remote_code=True)

            # decide load options
            use_cuda = torch.cuda.is_available()
            device_map = "auto" if use_cuda else None
            dtype = torch.float16 if use_cuda else torch.float32
            load_in_4bit = bool(self.load_in_4bit and use_cuda)

            try:
                # load base model
                self.llm_model = AutoModelForCausalLM.from_pretrained(
                    "microsoft/Phi-3-mini-4k-instruct",
                    device_map=device_map,
                    torch_dtype=dtype,
                    load_in_4bit=load_in_4bit,
                    trust_remote_code=True
                )
                # attach adapters if present in self.model_path
                if (self.model_path / "adapter_config.json").exists():
                    logger.info("Attaching PEFT adapters from %s", str(self.model_path))
                    try:
                        self.llm_model = PeftModel.from_pretrained(self.llm_model, str(self.model_path), is_trainable=False)
                    except Exception as e:
                        logger.warning("Failed to attach PEFT adapters: %s", e)
                self.llm_model.eval()
                logger.info("LLM loaded (device_map=%s, dtype=%s, 4bit=%s)", str(device_map), str(dtype), str(load_in_4bit))
            except Exception as e:
                logger.error("LLM load failed: %s", e)
                raise

    # ---------------------------
    # Ingestion
    # ---------------------------

    def ingest_pdf(self, file_path: str, doc_id: str) -> Dict[str, Any]:
        """
        Ingest a PDF:
          - extract text,
          - chunk (smart_chunk_text),
          - compute embedding for chunks,
          - add to FAISS index (in memory),
          - update metadata and documents lists and save metadata.pkl to persist.
        Note: we attempt to load resources if required.
        """
        # ensure resources available
        self._load_resources()

        logger.info("Ingesting PDF %s as doc_id=%s", file_path, doc_id)
        # 1. extract text
        try:
            full_text = ""
            with pdfplumber.open(file_path) as pdf:
                for p in pdf.pages:
                    text = p.extract_text()
                    if text:
                        full_text += text + "\n"
        except Exception as e:
            logger.error("Failed to read PDF: %s", e)
            raise ValueError(f"Could not read PDF: {e}")

        if len(full_text.strip()) < 30:
            raise ValueError("PDF is empty or unreadable (scanned images not supported).")

        chunks = smart_chunk_text(full_text, chunk_size=500, overlap=50)
        logger.info("Extracted %d chunks from PDF %s", len(chunks), file_path)

        # run filters & classifier to decide role per chunk
        new_metadata = []
        for i, c in enumerate(chunks):
            meta = {
                "source": doc_id,
                "doc_id": f"{doc_id}_chunk_{i}",
                "tags": [],
                "sentinel_label": None,
                "sentinel_score": 0.0,
                # default role -> public; may be changed by filters
                "role": "public"
            }
            # Layer 1 - hard filter
            hf = self.hard_filter.inspect(c)
            meta["tags"].extend(hf.get("tags", []))
            if hf.get("forced_role") == "admin":
                meta["role"] = "admin"
            # Layer 2 - optional sentinel classifier
            if self.sentinel and self.sentinel.available:
                try:
                    sres = self.sentinel.score(c)
                    meta["sentinel_label"] = sres.get("top_label")
                    meta["sentinel_score"] = sres.get("top_score", 0.0)
                    # if sentinel strongly indicates "confidential" or "pii", upgrade sensitivity
                    if meta["sentinel_label"] and meta["sentinel_score"] >= 0.85:
                        if any(lbl in meta["sentinel_label"].lower() for lbl in ("confidential", "pii", "internal", "financial")):
                            meta["role"] = "admin"
                            meta["tags"].append(f"sentinel:{meta['sentinel_label']}")
                except Exception as e:
                    logger.warning("Sentinel failed on chunk: %s", e)
            new_metadata.append(meta)

        # 3. compute embeddings for new chunks and add to FAISS
        try:
            new_embs = self.embedding_model.encode(chunks, convert_to_numpy=True)
            # if index is None, create a new index (flat L2); else append
            if self.faiss_index is None:
                dim = new_embs.shape[1]
                # Use IndexFlatIP (cosine-like) but we must normalize embeddings for IP to work like cosine
                index = faiss.IndexFlatIP(dim)
                faiss.normalize_L2(new_embs)
                index.add(new_embs.astype('float32'))
                self.faiss_index = index
                # create initial documents/metadata lists
                self.documents = chunks.copy()
                self.metadata = new_metadata.copy()
            else:
                # normalize embeddings
                faiss.normalize_L2(new_embs)
                self.faiss_index.add(new_embs.astype('float32'))
                # append docs & metadata
                self.documents.extend(chunks)
                self.metadata.extend(new_metadata)
        except Exception as e:
            logger.error("Failed to compute embeddings / add to faiss: %s", e)
            raise

        # persist updated metadata + documents (best-effort)
        try:
            os.makedirs(self.db_folder, exist_ok=True)
            meta_path = self.db_folder / "metadata.pkl"
            with open(meta_path, "wb") as f:
                pickle.dump({"metadata": self.metadata, "documents": self.documents}, f)
            # and save index to disk
            idx_path = self.db_folder / "faiss.index"
            faiss.write_index(self.faiss_index, str(idx_path))
            logger.info("Ingestion complete and persisted: %d new chunks", len(chunks))
        except Exception as e:
            logger.warning("Could not persist DB to disk: %s", e)

        return {"chunks_added": len(chunks), "doc_id": doc_id, "status": "success"}

    # ---------------------------
    # Query pipeline
    # ---------------------------
    def query(self, user_query: str, role: str, allowed_indices: Optional[List[int]] = None) -> Dict[str, Any]:
        """
        Query the RAG engine.
        - role: "admin" or "guest" (case-insensitive).
        - allowed_indices: optional list of chunk indices (Layer 3) to constrain the context (used by higher-level wrappers).
        The method enforces DB-level filtering so the LLM never sees disallowed chunks.
        """
        start = time.time()
        self._load_resources()

        role_norm = str(role).lower() if role else "guest"

        # If explicit allowed_indices provided, validate and use them
        candidate_results: List[Dict[str, Any]] = []

        if allowed_indices:
            # use allowed indices directly
            for idx in allowed_indices:
                if not isinstance(idx, int):
                    continue
                if 0 <= idx < len(self.documents):
                    candidate_results.append({
                        "content": self.documents[idx],
                        "meta": self.metadata[idx],
                        "score": 1.0
                    })
        else:
            # Compute query embedding and compare to all document embeddings using embedding_model
            try:
                docs = self.documents or []
                if not docs:
                    return {"answer": "No documents available.", "sources": [], "status": "empty"}
                # encode query and compute sims
                q_emb = self.embedding_model.encode([user_query], convert_to_numpy=True)[0]
                doc_embs = self.embedding_model.encode(docs, convert_to_numpy=True)
                sims = cosine_similarity([q_emb], doc_embs)[0]  # shape (n_docs,)
                # pick top N candidates (we pick top_k * 10 to allow filtering)
                top_n = max(self.top_k * 10, self.top_k + 5)
                top_idx = np.argsort(-sims)[:top_n]
                for idx in top_idx:
                    candidate_results.append({
                        "content": docs[int(idx)],
                        "meta": self.metadata[int(idx)],
                        "score": float(sims[int(idx)])
                    })
            except Exception as e:
                # fallback to FAISS search (if available)
                logger.warning("Embedding full-scan failed, falling back to FAISS search: %s", e)
                if self.faiss_index is not None:
                    try:
                        q_emb = self.embedding_model.encode([user_query], convert_to_numpy=True)
                        faiss.normalize_L2(q_emb)
                        scores, indices = self.faiss_index.search(q_emb.astype('float32'), self.top_k * 10)
                        for score, idx in zip(scores[0], indices[0]):
                            if idx >= 0 and idx < len(self.metadata):
                                candidate_results.append({
                                    "content": self.documents[int(idx)],
                                    "meta": self.metadata[int(idx)],
                                    "score": float(score)
                                })
                    except Exception as e2:
                        logger.error("FAISS fallback failed: %s", e2)
                        return {"answer": "Internal search failure.", "sources": [], "status": "error"}
                else:
                    return {"answer": "No search backend available.", "sources": [], "status": "error"}

        # Now apply DB-level RBAC filter (Layer 3)
        filtered_results = []
        sources = []
        for res in candidate_results:
            meta = res.get("meta", {}) or {}
            doc_role = meta.get("role", "public")
            # Guests can only access 'public' chunks
            if role_norm == "guest" and doc_role != "public":
                # drop
                continue
            filtered_results.append(res)
            sources.append(meta.get("source", "Unknown"))

            if len(filtered_results) >= self.top_k:
                break

        # If none left after RBAC, return access-denied style response (safe)
        if not filtered_results:
            return {
                "answer": "I cannot answer this based on the available documents (Access Denied or No Data).",
                "sources": [],
                "status": "blocked_or_empty"
            }

        # Build context from filtered_results
        context_text = "\n".join([f"- {r['content']}" for r in filtered_results])

        prompt = f"""{self.SYSTEM_PROMPT}
Context:
{context_text}
<|user|>
{user_query}
<|end|>
<|assistant|>
Answer:"""

        # tokenize and move inputs to model device
        inputs = self.llm_tokenizer(prompt, return_tensors="pt")
        model_device = next(self.llm_model.parameters()).device
        inputs = {k: v.to(model_device) for k, v in inputs.items()}

        # generate
        # generate
        try:
            with torch.no_grad():
                outputs = self.llm_model.generate(
                    **inputs,
                    max_new_tokens=256,
                    do_sample=True,  # Changed from False
                    temperature=0.7,  # Increased from 0.1
                    top_p=0.9,
                    pad_token_id=self.llm_tokenizer.eos_token_id
                )
            response_text = self.llm_tokenizer.decode(outputs[0], skip_special_tokens=True)
            answer = response_text.split("Answer:")[-1].strip()
        except Exception as e:
            logger.error("Generation failed: %s", e)
            return {"answer": "Model generation failed.", "sources": sources, "status": "error"}

        elapsed = time.time() - start
        logger.debug("Query processed in %.3fs (role=%s, candidates=%d, used=%d)", elapsed, role_norm, len(candidate_results), len(filtered_results))

        return {"answer": answer, "sources": list(dict.fromkeys(sources)), "status": "success"}

    # ---------------------------
    # Debug helpers
    # ---------------------------
    def list_chunks(self) -> List[Dict[str, Any]]:
        """
        Return metadata + snippets for debugging.
        """
        self._load_resources()
        out = []
        for i, meta in enumerate(self.metadata or []):
            snippet = (self.documents[i][:300] if i < len(self.documents) else "")
            out.append({
                "index": i,
                "doc_id": meta.get("doc_id", f"chunk_{i}"),
                "source": meta.get("source", "Unknown"),
                "role": meta.get("role", "public"),
                "tags": meta.get("tags", []),
                "sentinel_label": meta.get("sentinel_label"),
                "sentinel_score": meta.get("sentinel_score"),
                "snippet": snippet
            })
        return out

    def inspect_chunk(self, index: int) -> Dict[str, Any]:
        """
        Return detailed metadata for a specific chunk index.
        """
        self._load_resources()
        if index < 0 or index >= len(self.documents):
            raise IndexError("Invalid chunk index")
        meta = self.metadata[index]
        return {
            "index": index,
            "doc_id": meta.get("doc_id"),
            "source": meta.get("source"),
            "role": meta.get("role"),
            "tags": meta.get("tags"),
            "sentinel_label": meta.get("sentinel_label"),
            "sentinel_score": meta.get("sentinel_score"),
            "snippet": self.documents[index][:800]
        }

    # ---------------------------
    # Utilities
    # ---------------------------
    def get_gpu_status(self) -> str:
        if torch.cuda.is_available():
            # use 0th device memory
            mem = torch.cuda.memory_allocated() / 1024**3
            return f"{mem:.2f} GB"
        return "N/A"

# End of core.py

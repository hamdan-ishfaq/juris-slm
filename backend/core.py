"""
core.py - GuardRAG Logic Layer
Production-ready RAG engine with RBAC and lazy loading.
Matched to Project Chimera / California Tax DB.
"""

import os
import pickle
from pathlib import Path
from typing import List, Dict, Any, Tuple, Optional
import logging
import torch
import faiss
import numpy as np
from sentence_transformers import SentenceTransformer
from unsloth import FastLanguageModel

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class GuardRAG:
    """
    Guarded Retrieval-Augmented Generation Engine.
    Handles Search, Security (RBAC), and Generation.
    """
    
    # Strict system prompt to prevent hallucination
    SYSTEM_PROMPT = """<|system|>
You are a strict legal assistant. You must answer the user's question based ONLY on the Context provided below.
If the Context is empty or does not contain the answer, say "I cannot answer this based on the available documents."
DO NOT make up outside information.
<|end|>"""

    def __init__(
        self,
        db_folder: str = "./juris_faiss_db",
        model_path: str = "./juris_model_lora",
        embedding_model_name: str = "all-MiniLM-L6-v2",
        max_seq_length: int = 2048,
        load_in_4bit: bool = True,
        top_k: int = 3
    ):
        self.db_folder = Path(db_folder)
        self.model_path = Path(model_path)
        self.embedding_model_name = embedding_model_name
        self.max_seq_length = max_seq_length
        self.load_in_4bit = load_in_4bit
        self.top_k = top_k
        
        # Lazy-loaded components
        self.embedding_model = None
        self.llm_model = None
        self.llm_tokenizer = None
        self.faiss_index = None
        self.metadata = None
        self.documents = None
        
        logger.info("GuardRAG Engine initialized (Lazy Loading ON)")

    def _load_resources(self):
        """Lazy load models and database if not already loaded."""
        # 1. Load Embedding Model (CPU)
        if self.embedding_model is None:
            logger.info("Loading Embedding Model...")
            self.embedding_model = SentenceTransformer(self.embedding_model_name, device='cpu')

        # 2. Load FAISS DB
        if self.faiss_index is None:
            logger.info(f"Loading FAISS DB from {self.db_folder}...")
            index_path = self.db_folder / "faiss.index"
            meta_path = self.db_folder / "metadata.pkl"
            
            if not index_path.exists() or not meta_path.exists():
                raise FileNotFoundError("Database files missing! Did you copy 'juris_faiss_db' correctly?")
                
            self.faiss_index = faiss.read_index(str(index_path))
            with open(meta_path, 'rb') as f:
                data = pickle.load(f)
                self.metadata = data['metadata']
                self.documents = data['documents']

        # 3. Load LLM (GPU)
        if self.llm_model is None:
            logger.info(f"Loading LLM from {self.model_path}...")
            self.llm_model, self.llm_tokenizer = FastLanguageModel.from_pretrained(
                model_name=str(self.model_path),
                max_seq_length=self.max_seq_length,
                dtype=None,
                load_in_4bit=self.load_in_4bit,
            )
            FastLanguageModel.for_inference(self.llm_model)

    def query(self, user_query: str, role: str) -> Dict[str, Any]:
        """
        Main Pipeline: Search -> Guard -> Generate
        """
        try:
            # Ensure everything is loaded
            self._load_resources()
            
            # --- STEP 1: Search ---
            query_embedding = self.embedding_model.encode([user_query], convert_to_numpy=True)
            scores, indices = self.faiss_index.search(query_embedding.astype('float32'), self.top_k)
            
            raw_results = []
            for idx, score in zip(indices[0], scores[0]):
                if 0 <= idx < len(self.metadata):
                    raw_results.append({
                        "content": self.documents[idx],
                        "meta": self.metadata[idx],
                        "score": float(score)
                    })

            # --- STEP 2: Security Guard (RBAC) ---
            filtered_results = []
            sources = []
            
            for res in raw_results:
                doc_role = res['meta'].get('role', 'public')
                # RULE: Guests can ONLY see public. Admins see all.
                if role.lower() == 'guest' and doc_role != 'public':
                    logger.warning(f"BLOCKED access to doc {res['meta'].get('doc_id')} for Guest")
                    continue
                
                filtered_results.append(res['content'])
                sources.append(res['meta'].get('source', 'Unknown'))

            # --- STEP 3: Generation ---
            if not filtered_results:
                return {
                    "answer": "I cannot answer this based on the available documents (Access Denied or No Data).",
                    "sources": [],
                    "status": "blocked_or_empty"
                }

            context_text = "\n".join([f"- {chunk}" for chunk in filtered_results])
            
            prompt = f"""{self.SYSTEM_PROMPT}
Context:
{context_text}
<|user|>
{user_query}
<|end|>
<|assistant|>
Answer:"""

            inputs = self.llm_tokenizer(prompt, return_tensors="pt").to("cuda")
            
            with torch.no_grad():
                outputs = self.llm_model.generate(
                    **inputs, 
                    max_new_tokens=256,
                    do_sample=False,
                    temperature=0.1
                )
                
            response_text = self.llm_tokenizer.decode(outputs[0], skip_special_tokens=True)
            answer = response_text.split("Answer:")[-1].strip()

            return {
                "answer": answer,
                "sources": sources,
                "status": "success"
            }

        except Exception as e:
            logger.error(f"Error in engine: {str(e)}")
            raise e

    def get_gpu_status(self):
        """Helper to check VRAM."""
        if torch.cuda.is_available():
            mem = torch.cuda.memory_allocated() / 1024**3
            return f"{mem:.2f} GB"
        return "N/A"
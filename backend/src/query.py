# query.py
# src/query.py - Query processing logic
import time
import logging
from typing import Dict, Any, List, Optional
import numpy as np
from sklearn.metrics.pairwise import cosine_similarity
import faiss
import torch

from .models import ModelManager
from .security import SecurityManager

logger = logging.getLogger(__name__)

SYSTEM_PROMPT = """<|system|>
You are a skilled legal assistant named Juris.
Use the Context below to answer the user's question.
If the exact answer is not in the text, USE YOUR KNOWLEDGE to draft a reasonable response based on the available facts.
Do NOT say "I cannot answer" unless the context is completely irrelevant.
Be professional, detailed, and helpful.
<|end|>"""

class QueryManager:
    def __init__(self, config, model_manager: ModelManager, security_manager: SecurityManager, ingestion_manager):
        self.config = config
        self.model_manager = model_manager
        self.security_manager = security_manager
        self.ingestion_manager = ingestion_manager

    def query(self, user_query: str, role: str, allowed_indices: Optional[List[int]] = None) -> tuple:
        """
        Execute a query and return both the answer and trace data.
        
        Returns:
            Tuple of (answer_string, trace_dict)
        """
        start = time.time()
        self.model_manager.load_embedding_model()
        self.model_manager.load_llm()
        self.ingestion_manager._load_db()

        role_norm = str(role).lower()
        docs = self.ingestion_manager.documents
        metas = self.ingestion_manager.metadata

        # Initialize trace
        trace = {
            "query": user_query,
            "role": role_norm,
            "sentinel_scores": {},
            "retrieved_chunks": [],
            "filtering_log": [],
            "status": "success"
        }

        if not docs:
            return "No documents available.", trace

        candidate_results = []

        if allowed_indices:
            for idx in allowed_indices:
                if 0 <= idx < len(docs):
                    candidate_results.append({
                        "content": docs[idx],
                        "meta": metas[idx],
                        "score": 1.0
                    })
        else:
            # Embed query and search
            q_emb = self.model_manager.embedding_model.encode([user_query], convert_to_numpy=True)[0]
            doc_embs = self.model_manager.embedding_model.encode(docs, convert_to_numpy=True)
            sims = cosine_similarity([q_emb], doc_embs)[0]

            top_n = max(self.config.query.top_k * 10, self.config.query.top_k + 5)
            top_idx = np.argsort(-sims)[:top_n]
            for idx in top_idx:
                candidate_results.append({
                    "content": docs[int(idx)],
                    "meta": metas[int(idx)],
                    "score": float(sims[int(idx)])
                })

        # Filter by role
        filtered_results = []
        sources = []
        for res in candidate_results:
            meta = res.get("meta", {})
            # Treat missing/None roles as public to avoid blocking guest traffic
            doc_role = meta.get("role") or "public"
            
            if role_norm == "admin" or doc_role == "public":
                filtered_results.append(res)
                sources.append(meta.get("source", "Unknown"))
                trace["retrieved_chunks"].append({
                    "index": len(trace["retrieved_chunks"]),
                    "role": doc_role,
                    "score": res["score"],
                    "snippet": res["content"][:100]
                })
            else:
                trace["filtering_log"].append(f"Dropped: role={doc_role} (not accessible to {role_norm})")
            
            if len(filtered_results) >= self.config.query.top_k:
                break

        if not filtered_results:
            trace["status"] = "blocked"
            return "Access denied or no relevant documents.", trace

        # Build context and generate
        context = "\n".join([f"- {r['content']}" for r in filtered_results])
        prompt = f"{SYSTEM_PROMPT}\nContext:\n{context}\n<|user|>\n{user_query}\n<|end|>\n<|assistant|>\nAnswer:"

        inputs = self.model_manager.llm_tokenizer(prompt, return_tensors="pt")
        model_device = next(self.model_manager.llm_model.parameters()).device
        inputs = {k: v.to(model_device) for k, v in inputs.items()}

        with torch.no_grad():
            outputs = self.model_manager.llm_model.generate(
                **inputs,
                max_new_tokens=self.config.query.max_new_tokens,
                do_sample=True,
                temperature=self.config.query.temperature,
                top_p=self.config.query.top_p,
                pad_token_id=self.model_manager.llm_tokenizer.eos_token_id
            )
        response = self.model_manager.llm_tokenizer.decode(outputs[0], skip_special_tokens=True)
        answer = response.split("Answer:")[-1].strip()

        elapsed = time.time() - start
        trace["elapsed_seconds"] = elapsed
        logger.debug(f"Query processed in {elapsed:.3f}s")

        return answer, trace

        return {"answer": answer, "sources": list(dict.fromkeys(sources)), "status": "success"}
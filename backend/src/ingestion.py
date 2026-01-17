# ingestion.py
# src/ingestion.py - Document ingestion logic
import os
import pickle
import logging
from pathlib import Path
from typing import Dict, Any, List
import numpy as np
import faiss
import pdfplumber

from .utils import smart_chunk_text
from .security import SecurityManager
from .models import ModelManager

logger = logging.getLogger(__name__)

class IngestionManager:
    def __init__(self, config, model_manager: ModelManager, security_manager: SecurityManager):
        self.config = config
        self.model_manager = model_manager
        self.security_manager = security_manager
        self.db_path = Path(config.paths.faiss_db)
        self.index = None
        self.metadata: List[Dict[str, Any]] = []
        self.documents: List[str] = []

    def _load_db(self):
        index_path = self.db_path / "faiss.index"
        meta_path = self.db_path / "metadata.pkl"
        if index_path.exists() and meta_path.exists():
            self.index = faiss.read_index(str(index_path))
            with open(meta_path, "rb") as f:
                data = pickle.load(f)
                self.metadata = data.get("metadata", [])
                self.documents = data.get("documents", [])
            logger.info(f"Loaded FAISS DB with {len(self.documents)} chunks")

    def _save_db(self):
        os.makedirs(self.db_path, exist_ok=True)
        if self.index:
            faiss.write_index(self.index, str(self.db_path / "faiss.index"))
        with open(self.db_path / "metadata.pkl", "wb") as f:
            pickle.dump({"metadata": self.metadata, "documents": self.documents}, f)
        logger.info("DB persisted")

    def ingest_pdf(self, file_path: str, doc_id: str) -> Dict[str, Any]:
        self.model_manager.load_embedding_model()
        self._load_db()

        logger.info(f"Ingesting PDF {file_path} as {doc_id}")

        # Extract text
        full_text = ""
        with pdfplumber.open(file_path) as pdf:
            for page in pdf.pages:
                text = page.extract_text()
                if text:
                    full_text += text + "\n"

        if len(full_text.strip()) < 30:
            raise ValueError("PDF is empty or unreadable")

        # Chunk
        chunks = smart_chunk_text(full_text, self.config.ingestion.chunk_size, self.config.ingestion.chunk_overlap)

        # Assess each chunk
        new_metadata = []
        for i, chunk in enumerate(chunks):
            meta = {
                "source": doc_id,
                "doc_id": f"{doc_id}_chunk_{i}",
                "tags": [],
                "sentinel_label": None,
                "sentinel_score": 0.0,
                "role": "public"
            }
            assessment = self.security_manager.assess_chunk(chunk)
            meta.update(assessment)
            new_metadata.append(meta)

        # Embed and add to FAISS
        embeddings = self.model_manager.embedding_model.encode(chunks, convert_to_numpy=True)
        faiss.normalize_L2(embeddings)

        if self.index is None:
            dim = embeddings.shape[1]
            self.index = faiss.IndexFlatIP(dim)
            self.documents = chunks
            self.metadata = new_metadata
        else:
            self.index.add(embeddings.astype('float32'))
            self.documents.extend(chunks)
            self.metadata.extend(new_metadata)

        self._save_db()
        return {"chunks_added": len(chunks), "doc_id": doc_id}
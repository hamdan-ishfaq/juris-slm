# ingestion.py
# src/ingestion.py - Document ingestion logic with hierarchical parent-child chunking
import os
import pickle
import logging
from pathlib import Path
from typing import Dict, Any, List, Optional, Tuple
from uuid import UUID
import numpy as np
import faiss
import pdfplumber
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from .utils import smart_chunk_text
from .security import SecurityManager
from .models import ModelManager
from .db import Document, ParentChunk, AccessLevel

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

    async def ingest_pdf(
        self,
        file_path: str,
        user_id: UUID,
        db: AsyncSession,
        access_level: str = "level_2"
    ) -> Dict[str, Any]:
        """
        Ingest a PDF with hierarchical parent-child chunking strategy.
        
        Flow:
        1. Extract text from PDF
        2. Create Document record in PostgreSQL
        3. Create Parent Chunks (~1000 chars) and insert into parent_chunks table
        4. For each parent chunk, create Child Chunks (~200 chars)
        5. Embed child chunks and add to FAISS with parent_id metadata
        6. On FAISS failure, rollback PostgreSQL changes
        
        Args:
            file_path: Path to PDF file
            user_id: UUID of document owner
            db: SQLAlchemy async session
            access_level: Document access level (level_1, level_2, level_3)
        
        Returns:
            Dict with ingestion statistics
        """
        self.model_manager.load_embedding_model()
        self._load_db()

        filename = Path(file_path).name
        logger.info(f"Ingesting PDF {filename} for user {user_id} with access_level={access_level}")

        try:
            # Step 1: Extract text from PDF
            full_text = ""
            page_breaks = [0]  # Track where each page starts
            
            with pdfplumber.open(file_path) as pdf:
                for page_num, page in enumerate(pdf.pages, 1):
                    text = page.extract_text()
                    if text:
                        full_text += text + "\n"
                    page_breaks.append(len(full_text))

            if len(full_text.strip()) < 30:
                raise ValueError("PDF is empty or unreadable")

            logger.info(f"Extracted {len(full_text)} chars from {len(page_breaks)-1} pages")

            # Step 2: Create Document record in PostgreSQL
            document = Document(
                filename=filename,
                owner_id=user_id,
                access_level=AccessLevel(access_level)
            )
            db.add(document)
            await db.flush()  # Flush to get the ID without committing yet
            doc_id = document.id
            logger.info(f"Created Document record: {doc_id}")

            # Step 3: Create Parent Chunks (~1000 chars) and insert to DB
            parent_chunks_list = smart_chunk_text(
                full_text,
                chunk_size=1000,  # Larger chunks for parents
                overlap=150
            )

            parent_chunk_ids = []  # Store UUIDs of created parent chunks
            parent_chunk_objects = []
            
            for i, parent_content in enumerate(parent_chunks_list):
                # Find which page this chunk starts on
                char_pos = full_text.find(parent_content)
                page_num = next((j for j, pos in enumerate(page_breaks) if pos > char_pos), len(page_breaks)) - 1
                
                parent_chunk = ParentChunk(
                    doc_id=doc_id,
                    content=parent_content,
                    page_number=page_num if page_num >= 0 else None,
                    char_start=char_pos,
                    char_end=char_pos + len(parent_content)
                )
                db.add(parent_chunk)
                parent_chunk_objects.append(parent_chunk)

            await db.flush()  # Flush to get parent chunk IDs
            
            for pc in parent_chunk_objects:
                parent_chunk_ids.append(pc.id)
            
            logger.info(f"Created {len(parent_chunk_ids)} parent chunks")

            # Step 4: Create Child Chunks from each Parent and index in FAISS
            all_child_chunks = []
            all_child_metadata = []
            child_count = 0

            for parent_id, parent_content in zip(parent_chunk_ids, parent_chunks_list):
                # Split parent into smaller child chunks (~200 chars)
                child_chunks = smart_chunk_text(
                    parent_content,
                    chunk_size=200,  # Smaller chunks for children
                    overlap=50
                )

                for child_idx, child_content in enumerate(child_chunks):
                    all_child_chunks.append(child_content)
                    
                    # Assess chunk for security tags
                    assessment = self.security_manager.assess_chunk(child_content)
                    
                    # Create metadata with parent_id link
                    meta = {
                        "parent_id": str(parent_id),
                        "doc_id": str(doc_id),
                        "access_level": access_level,
                        "filename": filename,
                        "user_id": str(user_id),
                        "tags": assessment.get("tags", []),
                        "sentinel_label": assessment.get("sentinel_label"),
                        "sentinel_score": assessment.get("sentinel_score", 0.0),
                        "role": assessment.get("role", "public")
                    }
                    all_child_metadata.append(meta)
                    child_count += 1

            logger.info(f"Created {child_count} child chunks from parent chunks")

            # Step 5: Embed and add to FAISS
            if all_child_chunks:
                embeddings = self.model_manager.embedding_model.encode(
                    all_child_chunks,
                    convert_to_numpy=True
                )
                faiss.normalize_L2(embeddings)

                if self.index is None:
                    dim = embeddings.shape[1]
                    self.index = faiss.IndexFlatIP(dim)
                    self.documents = all_child_chunks
                    self.metadata = all_child_metadata
                    logger.info(f"Created new FAISS index with dimension {dim}")
                else:
                    self.index.add(embeddings.astype('float32'))
                    self.documents.extend(all_child_chunks)
                    self.metadata.extend(all_child_metadata)
                    logger.info(f"Added embeddings to existing FAISS index")

                self._save_db()
                logger.info("Persisted FAISS index and metadata")
            else:
                logger.warning("No child chunks created, skipping FAISS indexing")

            # Commit all database changes
            await db.commit()
            logger.info(f"✅ Successfully ingested {filename}: {child_count} chunks indexed")

            return {
                "doc_id": str(doc_id),
                "filename": filename,
                "parent_chunks_created": len(parent_chunk_ids),
                "child_chunks_created": child_count,
                "access_level": access_level,
                "status": "success"
            }

        except Exception as e:
            # Rollback on any error
            await db.rollback()
            logger.error(f"❌ Ingestion failed for {filename}: {str(e)}")
            raise
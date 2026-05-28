import asyncio
import uuid
from celery import Celery
from pathlib import Path
from sqlalchemy import select

from config import settings
from db import MatterDocument, get_db, async_session_factory
from services.document_parser import parse_document
from services.embeddings import embed_texts
from services.vector_store import delete_by_document_id, insert_chunk
import re

celery_app = Celery(
    "juris_worker",
    broker=settings.redis_url,
    backend=settings.redis_url
)

def chunk_text(text: str, max_chars: int = 1200) -> list[str]:
    text = re.sub(r"\n{3,}", "\n\n", text.strip())
    parts = re.split(r"\n\n+", text)
    chunks: list[str] = []
    buf = ""
    for part in parts:
        part = part.strip()
        if not part:
            continue
        if len(buf) + len(part) + 2 <= max_chars:
            buf = f"{buf}\n\n{part}".strip() if buf else part
        else:
            if buf:
                chunks.append(buf)
            if len(part) <= max_chars:
                buf = part
            else:
                for i in range(0, len(part), max_chars):
                    chunks.append(part[i : i + max_chars])
                buf = ""
    if buf:
        chunks.append(buf)
    return chunks

async def _process_document_async(document_id: uuid.UUID) -> dict:
    async with async_session_factory() as db:
        result = await db.execute(select(MatterDocument).where(MatterDocument.id == document_id))
        doc = result.scalar_one_or_none()
        
        if not doc:
            return {"status": "error", "message": "Document not found"}
            
        file_path = Path(doc.file_path)
        if not file_path.exists():
            return {"status": "error", "message": "File not found on disk"}
            
        # 1. Parse text
        text = parse_document(file_path, doc.filename)
        
        # 2. Chunk text
        chunks = chunk_text(text)
        
        # 3. Clean existing chunks
        await delete_by_document_id(db, document_id)
        
        # 4. Embed & Insert Chunks + Extract Graph
        vectors = embed_texts(chunks)
        from services.graph_extractor import extract_graph_from_text
        from db import GraphNode, GraphEdge
        
        for i, (content, vec) in enumerate(zip(chunks, vectors)):
            await insert_chunk(
                db,
                document_id=document_id,
                chunk_index=i,
                content=content,
                embedding=vec,
                metadata={"source": "contract", "title": doc.filename, "kind": "contract", "document_id": str(document_id)}
            )
            
            # Extract Graph Entities
            graph_data = await extract_graph_from_text(content)
            
            node_map = {}
            for node_data in graph_data.get("nodes", []):
                node_name = node_data.get("name")
                if not node_name: continue
                node = GraphNode(
                    document_id=document_id,
                    name=node_name,
                    type=node_data.get("type", "Concept"),
                    description=node_data.get("description", "")
                )
                db.add(node)
                node_map[node_name] = node
            
            await db.flush() # Ensure nodes have IDs
            
            for edge_data in graph_data.get("edges", []):
                src_name = edge_data.get("source")
                tgt_name = edge_data.get("target")
                rel = edge_data.get("relationship", "RELATES_TO")
                
                if src_name in node_map and tgt_name in node_map:
                    edge = GraphEdge(
                        source_node_id=node_map[src_name].id,
                        target_node_id=node_map[tgt_name].id,
                        relationship=rel,
                        chunk_index=i
                    )
                    db.add(edge)
                    
        await db.commit()
        return {"status": "success", "chunks": len(chunks)}

@celery_app.task
def process_document_task(document_id_str: str):
    doc_id = uuid.UUID(document_id_str)
    # Run the async loop inside the sync celery task
    loop = asyncio.get_event_loop()
    result = loop.run_until_complete(_process_document_async(doc_id))
    return result

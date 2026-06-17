import asyncio
import uuid
from celery import Celery
from pathlib import Path
from sqlalchemy import select

from config import settings
from db import MatterDocument, engine, async_session_factory
from services.advanced_chunking import hierarchical_chunk
from services.contextual_retrieval import build_embedding_text
from services.document_parser import parse_document
from services.embeddings import embed_texts
from services.vector_store import delete_by_document_id, insert_chunk

celery_app = Celery(
    "juris_worker",
    broker=settings.redis_url,
    backend=settings.redis_url
)


async def _process_document_async(document_id: uuid.UUID) -> dict:
    async with async_session_factory() as db:
        result = await db.execute(select(MatterDocument).where(MatterDocument.id == document_id))
        doc = result.scalar_one_or_none()

        if not doc:
            return {"status": "error", "message": "Document not found"}

        file_path = Path(doc.file_path)
        if not file_path.exists():
            return {"status": "error", "message": "File not found on disk"}

        text = parse_document(file_path, doc.filename)
        chunk_items = hierarchical_chunk(text)

        if not chunk_items:
            return {"status": "error", "message": "No text extracted from document"}

        await delete_by_document_id(db, document_id)

        embed_inputs: list[str] = []
        for item in chunk_items:
            meta = {
                "source": "contract",
                "title": doc.filename,
                "kind": "contract",
                "document_id": str(document_id),
                "confidentiality": doc.confidentiality,
                "matter_id": str(doc.matter_id),
                "parent_id": item.get("parent_id"),
                "parent_title": item.get("parent_title"),
                "parent_content": item.get("parent_content"),
                "child_index": item.get("child_index"),
            }
            if settings.contextual_retrieval_enabled:
                embed_inputs.append(build_embedding_text(item["content"], meta))
            else:
                embed_inputs.append(item["content"])

        vectors = embed_texts(embed_inputs)
        from services.graph_extractor import extract_graph_from_text
        from db import GraphNode, GraphEdge

        for i, (item, vec) in enumerate(zip(chunk_items, vectors)):
            meta = {
                "source": "contract",
                "title": doc.filename,
                "kind": "contract",
                "document_id": str(document_id),
                "confidentiality": doc.confidentiality,
                "matter_id": str(doc.matter_id),
                "parent_id": item.get("parent_id"),
                "parent_title": item.get("parent_title"),
                "parent_content": item.get("parent_content"),
                "child_index": item.get("child_index"),
            }
            await insert_chunk(
                db,
                document_id=document_id,
                chunk_index=i,
                content=item["content"],
                embedding=vec,
                metadata=meta,
            )

            graph_data = await extract_graph_from_text(item["content"])
            node_map = {}
            for node_data in graph_data.get("nodes", []):
                node_name = node_data.get("name")
                if not node_name:
                    continue
                node = GraphNode(
                    document_id=document_id,
                    name=node_name,
                    type=node_data.get("type", "Concept"),
                    description=node_data.get("description", ""),
                )
                db.add(node)
                node_map[node_name] = node

            await db.flush()

            for edge_data in graph_data.get("edges", []):
                src_name = edge_data.get("source")
                tgt_name = edge_data.get("target")
                rel = edge_data.get("relationship", "RELATES_TO")
                if src_name in node_map and tgt_name in node_map:
                    edge = GraphEdge(
                        source_node_id=node_map[src_name].id,
                        target_node_id=node_map[tgt_name].id,
                        relationship=rel,
                        chunk_index=i,
                    )
                    db.add(edge)

        await db.commit()
        return {"status": "success", "chunks": len(chunk_items)}


@celery_app.task
def process_document_task(document_id_str: str):
    """Run async ingest in an isolated event loop; dispose DB pool after each task."""
    doc_id = uuid.UUID(document_id_str)

    async def _run() -> dict:
        try:
            return await _process_document_async(doc_id)
        finally:
            await engine.dispose()

    return asyncio.run(_run())

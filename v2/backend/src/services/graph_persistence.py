"""Persist contract knowledge-graph nodes/edges for a document."""
from __future__ import annotations

import uuid

from sqlalchemy import delete as sa_delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from db import GraphEdge, GraphNode, MatterDocument
from services.graph_extractor import extract_graph_from_text


async def clear_document_graph(db: AsyncSession, document_id: uuid.UUID) -> None:
    node_result = await db.execute(select(GraphNode.id).where(GraphNode.document_id == document_id))
    node_ids = list(node_result.scalars().all())
    if not node_ids:
        return
    await db.execute(
        sa_delete(GraphEdge).where(
            (GraphEdge.source_node_id.in_(node_ids)) | (GraphEdge.target_node_id.in_(node_ids))
        )
    )
    await db.execute(sa_delete(GraphNode).where(GraphNode.id.in_(node_ids)))


async def persist_graph_from_text(
    db: AsyncSession,
    doc: MatterDocument,
    text: str,
    *,
    chunk_index: int = 0,
) -> dict[str, int]:
    graph_data = await extract_graph_from_text(text)
    await clear_document_graph(db, doc.id)

    node_map: dict[str, GraphNode] = {}
    nodes_created = 0
    edges_created = 0

    for node_data in graph_data.get("nodes", []):
        node_name = node_data.get("name")
        if not node_name:
            continue
        node = GraphNode(
            document_id=doc.id,
            org_id=doc.org_id,
            name=node_name,
            type=node_data.get("type", "Concept"),
            description=node_data.get("description", ""),
        )
        db.add(node)
        node_map[node_name] = node
        nodes_created += 1

    await db.flush()

    for edge_data in graph_data.get("edges", []):
        src_name = edge_data.get("source")
        tgt_name = edge_data.get("target")
        rel = edge_data.get("relationship", "RELATES_TO")
        if src_name in node_map and tgt_name in node_map:
            db.add(
                GraphEdge(
                    source_node_id=node_map[src_name].id,
                    target_node_id=node_map[tgt_name].id,
                    relationship=rel,
                    chunk_index=chunk_index,
                )
            )
            edges_created += 1

    return {"nodes": nodes_created, "edges": edges_created}

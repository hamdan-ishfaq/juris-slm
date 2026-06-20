import asyncio
import uuid
from celery import Celery
from pathlib import Path
from sqlalchemy import select

from config import settings
from db import MatterDocument, Matter, engine, async_session_factory
from services.advanced_chunking import hierarchical_chunk
from services.contextual_retrieval import build_embedding_text
from services.embeddings import embed_texts
from services.rls import set_rls_org_context
from services.vector_store import delete_by_document_id, insert_chunk

celery_app = Celery(
    "juris_worker",
    broker=settings.redis_url,
    backend=settings.redis_url,
)
celery_app.conf.update(
    task_time_limit=int(__import__("os").environ.get("CELERY_TASK_TIME_LIMIT", "600")),
    task_soft_time_limit=int(__import__("os").environ.get("CELERY_TASK_SOFT_TIME_LIMIT", "540")),
)


async def _process_document_async(document_id: uuid.UUID) -> dict:
    async with async_session_factory() as db:
        result = await db.execute(select(MatterDocument).where(MatterDocument.id == document_id))
        doc = result.scalar_one_or_none()

        if not doc:
            return {"status": "error", "message": "Document not found"}

        doc.ingest_status = "processing"
        doc.ingest_error = None
        await db.commit()

        await set_rls_org_context(db, doc.org_id)

        file_path = Path(doc.file_path)
        if not file_path.exists():
            doc.ingest_status = "failed"
            doc.ingest_error = "File not found on disk"
            await db.commit()
            return {"status": "error", "message": "File not found on disk"}

        from services.document_parser import parse_document_ex

        parsed = parse_document_ex(file_path, doc.filename)
        text = parsed.text
        ocr_used = parsed.ocr_used
        if not (text or "").strip():
            doc.ingest_status = "failed"
            doc.ingest_error = "No text extracted from document; upload TXT or enable OCR for scanned PDFs"
            doc.ocr_used = ocr_used
            await db.commit()
            return {
                "status": "error",
                "message": doc.ingest_error,
            }
        chunk_items = hierarchical_chunk(text)

        if not chunk_items:
            doc.ingest_status = "failed"
            doc.ingest_error = "No text extracted from document"
            await db.commit()
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
                "ocr_used": ocr_used,
            }
            if settings.contextual_retrieval_enabled:
                embed_inputs.append(build_embedding_text(item["content"], meta))
            else:
                embed_inputs.append(item["content"])

        vectors = embed_texts(embed_inputs)
        from db import GraphNode, GraphEdge, Matter

        matter = await db.get(Matter, doc.matter_id)
        org_id_str = str(doc.org_id or (matter.org_id if matter else "")) or None

        nodes_created = 0
        edges_created = 0

        from services.graph_extractor import extract_graph_from_text

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
                "ocr_used": ocr_used,
            }
            if org_id_str:
                meta["org_id"] = org_id_str
            await insert_chunk(
                db,
                document_id=document_id,
                chunk_index=i,
                content=item["content"],
                embedding=vec,
                metadata=meta,
            )

            graph_data = {"nodes": [], "edges": []}
            if settings.graph_extraction_enabled:
                graph_data = await extract_graph_from_text(item["content"])
            node_map = {}
            for node_data in graph_data.get("nodes", []):
                node_name = node_data.get("name")
                if not node_name:
                    continue
                node = GraphNode(
                    document_id=document_id,
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
                    edge = GraphEdge(
                        source_node_id=node_map[src_name].id,
                        target_node_id=node_map[tgt_name].id,
                        relationship=rel,
                        chunk_index=i,
                    )
                    db.add(edge)
                    edges_created += 1

        doc.ingest_status = "processed"
        doc.ocr_used = ocr_used
        doc.ingest_error = None
        await db.commit()
        import logging

        logging.getLogger("jurisguard.worker").info(
            "graph_yield doc_id=%s chunks=%s nodes=%s edges=%s ocr=%s",
            document_id,
            len(chunk_items),
            nodes_created,
            edges_created,
            ocr_used,
        )
        return {
            "status": "success",
            "chunks": len(chunk_items),
            "graph_nodes": nodes_created,
            "graph_edges": edges_created,
        }


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


@celery_app.task
def gap_analysis_task(job_id: str):
    async def _run() -> dict:
        from db import User
        from services.agents.gap_analysis import run_gap_analysis
        from services.workflow_jobs import get_job, update_job

        job = get_job(job_id)
        if not job:
            return {"status": "error", "message": "Job not found"}
        meta = job.get("meta") or {}
        update_job(job_id, status="running", progress_step="extract_obligations")
        try:
            async with async_session_factory() as db:
                user = await db.get(User, uuid.UUID(meta["user_id"]))
                if not user:
                    raise ValueError("User not found")
                report = await run_gap_analysis(
                    db,
                    matter_id=uuid.UUID(meta["matter_id"]),
                    document_id=uuid.UUID(meta["document_id"]),
                    user=user,
                    baseline=meta.get("baseline", "gdpr"),
                )
                await db.commit()
            update_job(job_id, status="completed", progress_step="finalize_report", report=report)
            return {"status": "completed", "job_id": job_id}
        except Exception as exc:
            update_job(job_id, status="failed", error=str(exc)[:500])
            return {"status": "failed", "error": str(exc)}
        finally:
            await engine.dispose()

    return asyncio.run(_run())


@celery_app.task
def chat_task(job_id: str):
    async def _run() -> dict:
        from db import User
        from routers.chat import _audit_chat, _resolve_thread
        from routers.threads import append_message
        from services.rag import answer_question, load_thread_history
        from services.workflow_jobs import get_job, update_job

        job = get_job(job_id)
        if not job:
            return {"status": "error", "message": "Job not found"}
        meta = job.get("meta") or {}
        update_job(job_id, status="running", progress_step="retrieve")
        try:
            async with async_session_factory() as db:
                user = await db.get(User, uuid.UUID(meta["user_id"]))
                if not user:
                    raise ValueError("User not found")
                from schemas import ChatRequest

                body = ChatRequest(
                    message=meta["message"],
                    use_law_corpus=meta.get("use_law_corpus", True),
                    use_hyde=meta.get("use_hyde", False),
                    thread_id=uuid.UUID(meta["thread_id"]) if meta.get("thread_id") else None,
                )
                thread_id = await _resolve_thread(db, user, body)
                await append_message(db, thread_id=thread_id, role="user", content=body.message, org_id=user.org_id)
                history = await load_thread_history(db, thread_id, max_turns=settings.chat_history_turns)
                await db.commit()

                update_job(job_id, progress_step="generate")
                result = await answer_question(
                    db,
                    body.message,
                    use_law_corpus=body.use_law_corpus,
                    user=user,
                    use_hyde=body.use_hyde,
                    history=history,
                )
                await append_message(
                    db,
                    thread_id=thread_id,
                    role="assistant",
                    content=result["answer"],
                    sources=result.get("sources"),
                    model=result.get("model"),
                    org_id=user.org_id,
                )
                await _audit_chat(
                    db,
                    user,
                    question=body.message,
                    result=result,
                    thread_id=thread_id,
                    use_law_corpus=body.use_law_corpus,
                )
                await db.commit()
            report = {
                "answer": result["answer"],
                "model": result["model"],
                "sources": result.get("sources") or [],
                "thread_id": str(thread_id),
                "cached": result.get("cached", False),
            }
            update_job(job_id, status="completed", progress_step="done", report=report)
            return {"status": "completed", "job_id": job_id}
        except Exception as exc:
            update_job(job_id, status="failed", error=str(exc)[:500])
            return {"status": "failed", "error": str(exc)}
        finally:
            await engine.dispose()

    return asyncio.run(_run())


@celery_app.task
def ingest_corpus_task(source_id: str):
    async def _run() -> dict:
        from db import CorpusSource
        from services.corpus_ingest import ingest_file_corpus

        async with async_session_factory() as db:
            src = await db.get(CorpusSource, uuid.UUID(source_id))
            if not src:
                return {"status": "error", "message": "Source not found"}
            src.status = "processing"
            await db.commit()
            try:
                count = await ingest_file_corpus(
                    db,
                    file_path=Path(src.file_path),
                    source=src.slug,
                    title=src.title,
                    document_id=src.document_id,
                    jurisdiction=src.jurisdiction,
                )
                src.chunk_count = count
                src.status = "processed" if count > 0 else "failed"
                await db.commit()
                return {"status": src.status, "chunks": count}
            except Exception as exc:
                src.status = "failed"
                await db.commit()
                return {"status": "failed", "error": str(exc)}
            finally:
                await engine.dispose()

    return asyncio.run(_run())

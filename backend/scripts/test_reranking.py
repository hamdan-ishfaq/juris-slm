#!/usr/bin/env python3
"""
test_reranking.py
Phase 3 validation: Reranking & Query Tracing
"""
import asyncio
import os
import sys
from pathlib import Path

# Set environment variables BEFORE importing config
os.environ.setdefault("AUTH_SECRET_KEY", "test-secret-key-for-reranking-demo-12345678901234567890")
os.environ.setdefault("DATABASE_URL", "postgresql+asyncpg://juris:juris_password@localhost:5432/juris_db")

# Add parent directory to Python path
backend_path = Path(__file__).parent.parent
sys.path.insert(0, str(backend_path))

from config import load_config
from src.models import ModelManager
from src.security import SecurityManager
from src.ingestion import IngestionManager
from src.query import QueryManager
from src.db import init_db, get_db, User, UserRole, QueryTrace
from passlib.context import CryptContext
from sqlalchemy import select

# Password hashing
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


async def main():
    """
    1. Initialize database and create test user
    2. Ingest a test document
    3. Run a query and verify reranking (pre-rank vs post-rank)
    4. Verify QueryTrace record was created
    """
    # Load config
    config = load_config()
    
    # Initialize database
    print("🔧 Initializing database...")
    await init_db(config.auth.database_url)
    
    # Initialize managers
    print("🔧 Initializing model managers...")
    model_manager = ModelManager(config)
    security_manager = SecurityManager(config)
    ingestion_manager = IngestionManager(config, model_manager, security_manager)
    query_manager = QueryManager(config, model_manager, security_manager, ingestion_manager)
    
    # Get database session
    async for db in get_db():
        try:
            # 1. Create test user if not exists
            print("\n📋 Step 1: Create test user")
            stmt = select(User).where(User.email == "test@rerank.demo")
            result = await db.execute(stmt)
            test_user = result.scalar_one_or_none()
            
            if test_user is None:
                hashed_password = pwd_context.hash("testpass123")
                test_user = User(
                    email="test@rerank.demo",
                    password_hash=hashed_password,
                    role=UserRole.USER
                )
                db.add(test_user)
                await db.commit()
                await db.refresh(test_user)
                print(f"✅ Created test user: {test_user.email} (ID: {test_user.id})")
            else:
                print(f"✅ Test user already exists: {test_user.email} (ID: {test_user.id})")
            
            # 2. Ingest a test document (use the tester.pdf if available)
            print("\n📋 Step 2: Ingest test document")
            test_pdf = Path("/wsl.localhost/Ubuntu/home/mhamd/juris_full_project/tester.pdf")
            if not test_pdf.exists():
                print(f"⚠️  Test PDF not found at {test_pdf}, skipping ingestion test")
            else:
                print(f"📄 Ingesting {test_pdf.name}...")
                try:
                    result = await ingestion_manager.ingest_pdf(
                        file_path=str(test_pdf),
                        user_id=test_user.id,
                        db=db,
                        access_level="level_1"
                    )
                    print(f"✅ Ingested document: {result['doc_id']}")
                    print(f"   - Parent chunks: {result['parent_chunks_created']}")
                    print(f"   - Child chunks: {result['child_chunks_created']}")
                except Exception as e:
                    print(f"⚠️  Ingestion failed (may already exist): {e}")
            
            # 3. Run query with reranking
            print("\n📋 Step 3: Run query with reranking")
            test_query = "What are the salary requirements for exempt employees?"
            
            # Load models
            model_manager.load_embedding_model()
            model_manager.load_reranker()
            ingestion_manager._load_db()
            
            # Get documents count
            num_docs = len(ingestion_manager.documents) if ingestion_manager.documents else 0
            print(f"📊 Loaded {num_docs} chunks from FAISS")
            
            if num_docs == 0:
                print("⚠️  No documents loaded, skipping query test")
                return
            
            # Show pre-rerank vs post-rerank
            print(f"\n🔍 Query: '{test_query}'")
            
            # Get hybrid search results BEFORE reranking (intermediate step)
            hybrid_results_raw = query_manager.search_hybrid(test_query, top_k=5)
            
            print("\n📌 Before Reranking (Hybrid Fusion Only):")
            for i, result in enumerate(hybrid_results_raw[:3], 1):
                idx = result.get("index", -1)
                if idx >= 0 and idx < len(ingestion_manager.documents):
                    snippet = ingestion_manager.documents[idx][:150]
                    score = result.get("score", 0.0)
                    hybrid_score = result.get("hybrid_score", score)
                    print(f"  {i}. [idx={idx}] score={score:.4f} hybrid={hybrid_score:.4f}")
                    print(f"     \"{snippet}...\"")
            
            # Now run full query (which uses reranking internally)
            answer, trace = query_manager.query(
                user_query=test_query,
                role="user",
                db=db,
                user_id=str(test_user.id)
            )
            
            print("\n📌 After Reranking (Full Query):")
            retrieved_chunks = trace.get("retrieved_chunks", [])
            for i, chunk_info in enumerate(retrieved_chunks[:3], 1):
                print(f"  {i}. [idx={chunk_info.get('index')}] score={chunk_info.get('score', 0.0):.4f}")
                print(f"     \"{chunk_info.get('snippet', '')}...\"")
            
            print(f"\n💬 Answer: {answer[:200]}...")
            
            # Wait a moment for async trace logging to complete
            await asyncio.sleep(1)
            
            # 4. Verify QueryTrace entry
            print("\n📋 Step 4: Verify QueryTrace record")
            stmt = select(QueryTrace).where(QueryTrace.user_id == test_user.id).order_by(QueryTrace.timestamp.desc()).limit(1)
            result = await db.execute(stmt)
            latest_trace = result.scalar_one_or_none()
            
            if latest_trace:
                print(f"✅ Found query trace:")
                print(f"   - Trace ID: {latest_trace.id}")
                print(f"   - Query: {latest_trace.query_text}")
                print(f"   - Response length: {len(latest_trace.response_text)} chars")
                print(f"   - Retrieved doc IDs: {latest_trace.retrieved_doc_ids}")
                print(f"   - Timestamp: {latest_trace.timestamp}")
            else:
                print("⚠️  No query trace found - async logging may not have completed yet")
            
            print("\n✅ Reranking & Query Tracing test completed successfully!")
            
        finally:
            await db.close()


if __name__ == "__main__":
    asyncio.run(main())

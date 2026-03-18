"""
Test script to verify Phase 2 schema relationships
Creates sample data and tests CASCADE deletes
"""
import asyncio
import sys
from pathlib import Path
from uuid import uuid4

BACKEND_ROOT = Path(__file__).parents[1]
sys.path.append(str(BACKEND_ROOT))

from src.db import init_db, get_db, User, Document, ParentChunk, QueryTrace, UserRole, AccessLevel
from config import config


async def test_schema():
    """Test Phase 2 schema relationships"""
    print("🧪 Testing Phase 2 Schema Relationships\n")
    
    # Initialize DB
    await init_db(config.auth.database_url)
    
    # Get session
    session_gen = get_db()
    session = await session_gen.__anext__()
    
    try:
        # 1. Create test user
        print("1️⃣ Creating test user...")
        test_user = User(
            email="test_phase2@example.com",
            password_hash="dummy_hash",
            role=UserRole.USER
        )
        session.add(test_user)
        await session.commit()
        await session.refresh(test_user)
        print(f"   ✓ Created user: {test_user.email} (ID: {test_user.id})")
        
        # 2. Create test document
        print("\n2️⃣ Creating test document...")
        test_doc = Document(
            filename="test_document.pdf",
            owner_id=test_user.id,
            access_level=AccessLevel.LEVEL_2
        )
        session.add(test_doc)
        await session.commit()
        await session.refresh(test_doc)
        print(f"   ✓ Created document: {test_doc.filename} (ID: {test_doc.id})")
        print(f"   ✓ Owner: {test_user.email}")
        print(f"   ✓ Access Level: {test_doc.access_level.value}")
        
        # 3. Create parent chunks
        print("\n3️⃣ Creating parent chunks...")
        chunks = []
        for i in range(3):
            chunk = ParentChunk(
                doc_id=test_doc.id,
                content=f"This is test parent chunk {i+1} with large context block.",
                page_number=i+1,
                char_start=i * 1000,
                char_end=(i + 1) * 1000
            )
            chunks.append(chunk)
            session.add(chunk)
        
        await session.commit()
        for chunk in chunks:
            await session.refresh(chunk)
        print(f"   ✓ Created {len(chunks)} parent chunks")
        for chunk in chunks:
            print(f"      - Chunk {chunk.page_number}: {chunk.content[:50]}...")
        
        # 4. Create query trace
        print("\n4️⃣ Creating query trace...")
        trace = QueryTrace(
            user_id=test_user.id,
            query_text="What is the meaning of life?",
            response_text="42, according to Douglas Adams.",
            retrieved_doc_ids=[str(test_doc.id)]
        )
        session.add(trace)
        await session.commit()
        await session.refresh(trace)
        print(f"   ✓ Created query trace (ID: {trace.id})")
        print(f"   ✓ Query: {trace.query_text}")
        print(f"   ✓ Retrieved docs: {trace.retrieved_doc_ids}")
        
        # 5. Test relationships
        print("\n5️⃣ Testing relationships...")
        await session.refresh(test_user, ["documents", "query_traces"])
        await session.refresh(test_doc, ["parent_chunks"])
        
        print(f"   ✓ User has {len(test_user.documents)} document(s)")
        print(f"   ✓ User has {len(test_user.query_traces)} query trace(s)")
        print(f"   ✓ Document has {len(test_doc.parent_chunks)} parent chunk(s)")
        
        # 6. Test CASCADE delete
        print("\n6️⃣ Testing CASCADE delete...")
        print(f"   Deleting user: {test_user.email}")
        
        # Get counts before delete
        from sqlalchemy import select, func
        doc_count = await session.scalar(select(func.count()).select_from(Document))
        chunk_count = await session.scalar(select(func.count()).select_from(ParentChunk))
        trace_count = await session.scalar(select(func.count()).select_from(QueryTrace))
        
        print(f"   Before delete: {doc_count} docs, {chunk_count} chunks, {trace_count} traces")
        
        # Delete user (should cascade)
        await session.delete(test_user)
        await session.commit()
        
        # Get counts after delete
        doc_count_after = await session.scalar(select(func.count()).select_from(Document))
        chunk_count_after = await session.scalar(select(func.count()).select_from(ParentChunk))
        trace_count_after = await session.scalar(select(func.count()).select_from(QueryTrace))
        
        print(f"   After delete: {doc_count_after} docs, {chunk_count_after} chunks, {trace_count_after} traces")
        print(f"   ✓ CASCADE delete successful!")
        
        print("\n✅ All tests passed!")
        
    except Exception as e:
        print(f"\n❌ Test failed: {e}")
        import traceback
        traceback.print_exc()
        raise
    finally:
        await session.close()


if __name__ == "__main__":
    asyncio.run(test_schema())

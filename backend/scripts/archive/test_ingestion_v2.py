"""
Test script for Phase 2 hierarchical ingestion pipeline
Tests parent-child chunking with database integration
"""
import asyncio
import sys
from pathlib import Path
from uuid import uuid4
import tempfile

BACKEND_ROOT = Path(__file__).parents[1]
sys.path.append(str(BACKEND_ROOT))

from src.db import init_db, get_db, User, Document, ParentChunk, UserRole, AccessLevel
from src.ingestion import IngestionManager
from src.models import ModelManager
from src.security import SecurityManager
from config import config


def create_dummy_pdf(file_path: str) -> None:
    """Create a simple test PDF with text content"""
    try:
        from reportlab.lib.pagesizes import letter
        from reportlab.pdfgen import canvas
    except ImportError:
        # Fallback: create a minimal PDF manually
        print("⚠️  reportlab not available, creating minimal test PDF...")
        with open(file_path, 'wb') as f:
            # Minimal PDF structure
            f.write(b"""%PDF-1.4
1 0 obj
<< /Type /Catalog /Pages 2 0 R >>
endobj
2 0 obj
<< /Type /Pages /Kids [3 0 R] /Count 1 >>
endobj
3 0 obj
<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] /Contents 4 0 R /Resources << /Font << /F1 5 0 R >> >> >>
endobj
4 0 obj
<< /Length 500 >>
stream
BT
/F1 12 Tf
50 750 Td
(This is a test PDF document for hierarchical ingestion.) Tj
0 -20 Td
(It contains multiple paragraphs of text to test parent and child chunking.) Tj
0 -20 Td
(Parent chunks should be around 1000 characters.) Tj
0 -20 Td
(Child chunks should be around 200 characters.) Tj
0 -20 Td
(This allows for hierarchical retrieval during query processing.) Tj
0 -40 Td
(Paragraph 2: Additional content to ensure sufficient text for testing.) Tj
0 -20 Td
(The ingestion system should create parent chunks and then split them into children.) Tj
0 -20 Td
(Each child chunk will be embedded separately and stored with parent_id metadata.) Tj
0 -20 Td
(This enables efficient hierarchical retrieval and context expansion.) Tj
ET
endstream
endobj
5 0 obj
<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>
endobj
xref
0 6
0000000000 65535 f 
0000000009 00000 n 
0000000058 00000 n 
0000000115 00000 n 
0000000244 00000 n 
0000000793 00000 n 
trailer
<< /Size 6 /Root 1 0 R >>
startxref
891
%%EOF
""")
        return
    
    c = canvas.Canvas(file_path, pagesize=letter)
    
    # Add test content
    text = """This is a test PDF document for hierarchical ingestion testing.

Paragraph 1:
It contains multiple paragraphs of text to test parent and child chunking. Parent chunks should be around 1000 characters. Child chunks should be around 200 characters. This allows for hierarchical retrieval during query processing.

Paragraph 2:
Additional content to ensure sufficient text for testing. The ingestion system should create parent chunks and then split them into children. Each child chunk will be embedded separately and stored with parent_id metadata. This enables efficient hierarchical retrieval and context expansion.

Paragraph 3:
More test content goes here. The system needs enough text to create multiple parent chunks and test the hierarchical indexing strategy. This is critical for Phase 2 evaluation and validation.

Paragraph 4:
Final test content. The hierarchical approach allows parents to maintain document structure while children enable fine-grained semantic search. This dual-indexing strategy balances retrieval precision and contextual completeness."""

    y = 750
    for line in text.split('\n'):
        if y < 50:
            c.showPage()
            y = 750
        c.drawString(50, y, line)
        y -= 20
    
    c.save()
    print(f"✓ Created test PDF: {file_path}")


async def test_hierarchical_ingestion():
    """Test the Phase 2 hierarchical ingestion pipeline"""
    print("\n" + "=" * 70)
    print("🧪 PHASE 2 HIERARCHICAL INGESTION TEST")
    print("=" * 70 + "\n")
    
    # Initialize database
    print("1️⃣ Initializing database...")
    await init_db(config.auth.database_url)
    print("   ✓ Database initialized\n")
    
    # Get database session
    session_gen = get_db()
    db = await session_gen.__anext__()
    
    try:
        # Create test user
        print("2️⃣ Creating test user...")
        test_user = User(
            email="test_ingestion_v2@example.com",
            password_hash="dummy_hash",
            role=UserRole.USER
        )
        db.add(test_user)
        await db.commit()
        await db.refresh(test_user)
        print(f"   ✓ Created user: {test_user.email}")
        print(f"   ✓ User ID: {test_user.id}\n")
        
        # Create test PDF
        print("3️⃣ Creating test PDF...")
        with tempfile.NamedTemporaryFile(suffix=".pdf", delete=False) as tmp:
            pdf_path = tmp.name
        create_dummy_pdf(pdf_path)
        print(f"   ✓ Test PDF created: {pdf_path}\n")
        
        # Initialize ingestion manager
        print("4️⃣ Initializing IngestionManager...")
        model_manager = ModelManager(config)
        security_manager = SecurityManager(config)
        ingestion_manager = IngestionManager(config, model_manager, security_manager)
        print("   ✓ IngestionManager initialized\n")
        
        # Ingest PDF
        print("5️⃣ Ingesting PDF with hierarchical chunking...")
        result = await ingestion_manager.ingest_pdf(
            file_path=pdf_path,
            user_id=test_user.id,
            db=db,
            access_level="level_2"
        )
        print(f"   ✓ Ingestion completed:")
        print(f"     - Document ID: {result['doc_id']}")
        print(f"     - Parent chunks: {result['parent_chunks_created']}")
        print(f"     - Child chunks: {result['child_chunks_created']}")
        print(f"     - Access level: {result['access_level']}\n")
        
        doc_id = result['doc_id']
        parent_chunks_expected = result['parent_chunks_created']
        child_chunks_expected = result['child_chunks_created']
        
        # Verify Database: Count parent chunks
        print("6️⃣ Verifying Database Integration...")
        from sqlalchemy import select, func
        
        parent_count_result = await db.execute(
            select(func.count()).select_from(ParentChunk).where(ParentChunk.doc_id == doc_id)
        )
        parent_count = parent_count_result.scalar()
        
        print(f"   ✓ Parent chunks in DB: {parent_count}")
        if parent_count == parent_chunks_expected:
            print(f"     ✅ Matches expected count ({parent_chunks_expected})\n")
        else:
            print(f"     ❌ Expected {parent_chunks_expected}, got {parent_count}\n")
            raise AssertionError(f"Parent chunk count mismatch")
        
        # Get actual parent chunks
        parent_chunks_result = await db.execute(
            select(ParentChunk).where(ParentChunk.doc_id == doc_id)
        )
        parent_chunks_db = parent_chunks_result.scalars().all()
        print(f"   ✓ Retrieved {len(parent_chunks_db)} parent chunks from DB")
        for i, pc in enumerate(parent_chunks_db[:3], 1):
            print(f"     - Parent {i}: {len(pc.content)} chars, page {pc.page_number}")
        print()
        
        # Verify Vector Store: Check metadata has parent_id
        print("7️⃣ Verifying Vector Store Integration...")
        
        if ingestion_manager.metadata:
            print(f"   ✓ FAISS metadata entries: {len(ingestion_manager.metadata)}")
            
            # Check first few metadata entries
            has_parent_id = all("parent_id" in meta for meta in ingestion_manager.metadata)
            has_doc_id = all("doc_id" in meta for meta in ingestion_manager.metadata)
            has_access_level = all("access_level" in meta for meta in ingestion_manager.metadata)
            
            print(f"   ✓ All metadata has 'parent_id': {has_parent_id} {'✅' if has_parent_id else '❌'}")
            print(f"   ✓ All metadata has 'doc_id': {has_doc_id} {'✅' if has_doc_id else '❌'}")
            print(f"   ✓ All metadata has 'access_level': {has_access_level} {'✅' if has_access_level else '❌'}")
            
            # Print sample metadata
            print(f"\n   Sample metadata from first child chunk:")
            sample_meta = ingestion_manager.metadata[0]
            for key, value in list(sample_meta.items())[:8]:
                if key == "parent_id":
                    print(f"     - {key}: {value} 🔗 (links to parent chunk)")
                else:
                    print(f"     - {key}: {value}")
            print()
            
            if not (has_parent_id and has_doc_id and has_access_level):
                raise AssertionError("Missing critical metadata fields")
        else:
            print("   ❌ No FAISS metadata found\n")
            raise AssertionError("FAISS metadata is empty")
        
        # Verify FAISS index
        print("8️⃣ Verifying FAISS Index...")
        if ingestion_manager.index:
            num_vectors = ingestion_manager.index.ntotal
            print(f"   ✓ FAISS index contains: {num_vectors} vectors")
            if num_vectors == len(ingestion_manager.metadata):
                print(f"     ✅ Vectors match metadata count\n")
            else:
                print(f"     ❌ Mismatch: {num_vectors} vectors vs {len(ingestion_manager.metadata)} metadata\n")
                raise AssertionError("FAISS vector count mismatch")
        else:
            print("   ❌ FAISS index is None\n")
            raise AssertionError("FAISS index not created")
        
        # Test hierarchical link
        print("9️⃣ Testing Hierarchical Links...")
        parent_ids_in_db = {str(pc.id) for pc in parent_chunks_db}
        parent_ids_in_metadata = {meta.get("parent_id") for meta in ingestion_manager.metadata}
        
        matching_parents = parent_ids_in_db & parent_ids_in_metadata
        print(f"   ✓ Parent chunks in DB: {len(parent_ids_in_db)}")
        print(f"   ✓ Unique parent_ids in metadata: {len(parent_ids_in_metadata)}")
        print(f"   ✓ Matching parent_ids: {len(matching_parents)} {'✅' if matching_parents else '❌'}\n")
        
        if not matching_parents:
            raise AssertionError("No matching parent_ids between DB and FAISS metadata")
        
        # Final verdict
        print("=" * 70)
        print("✅ INGESTION SUCCESS")
        print("=" * 70)
        print("""
Hierarchical Ingestion Pipeline Working Correctly:
  ✅ Database: Documents and ParentChunks created
  ✅ Child Chunks: Created and embedded in FAISS
  ✅ Metadata: parent_id links established
  ✅ Hierarchical Structure: Parent-child relationship validated
  ✅ Access Control: access_level tracked per document

Ready for Phase 2 evaluation!
""")
        return True
        
    except Exception as e:
        print(f"\n❌ TEST FAILED: {e}")
        import traceback
        traceback.print_exc()
        return False
    
    finally:
        await db.close()


if __name__ == "__main__":
    result = asyncio.run(test_hierarchical_ingestion())
    sys.exit(0 if result else 1)

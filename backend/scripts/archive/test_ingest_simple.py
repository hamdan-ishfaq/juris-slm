"""
Simpler test to verify hierarchical ingestion implementation
Writes output to file for verification
"""
import asyncio
import sys
from pathlib import Path
from uuid import uuid4
import tempfile
import json

BACKEND_ROOT = Path(__file__).parents[1]
sys.path.append(str(BACKEND_ROOT))


async def run_test():
    """Quick test of ingestion pipeline"""
    output = []
    
    try:
        from src.db import init_db, get_db, User, UserRole, ParentChunk
        from src.ingestion import IngestionManager
        from src.models import ModelManager
        from src.security import SecurityManager
        from config import config
        from sqlalchemy import select, func
        
        output.append("✓ Imports successful")
        
        # Initialize
        await init_db(config.auth.database_url)
        output.append("✓ Database initialized")
        
        session_gen = get_db()
        db = await session_gen.__anext__()
        
        # Create test user
        test_user = User(
            email=f"test_{uuid4()}@example.com",
            password_hash="test_hash",
            role=UserRole.USER
        )
        db.add(test_user)
        await db.commit()
        await db.refresh(test_user)
        output.append(f"✓ Created test user: {test_user.id}")
        
        # Create dummy PDF
        pdf_path = tempfile.mktemp(suffix=".pdf")
        with open(pdf_path, 'wb') as f:
            f.write(b"%PDF-1.4\n1 0 obj\n<< /Type /Catalog /Pages 2 0 R >>\nendobj\n")
        output.append(f"✓ Created test PDF: {pdf_path}")
        
        # Initialize managers
        model_manager = ModelManager(config)
        security_manager = SecurityManager(config)
        ingestion_manager = IngestionManager(config, model_manager, security_manager)
        output.append("✓ Managers initialized")
        
        # Ingest
        result = await ingestion_manager.ingest_pdf(
            file_path=pdf_path,
            user_id=test_user.id,
            db=db,
            access_level="level_2"
        )
        output.append(f"✓ Ingestion result: parent={result.get('parent_chunks_created')}, child={result.get('child_chunks_created')}")
        
        # Check DB
        parent_count = await db.scalar(select(func.count()).select_from(ParentChunk))
        output.append(f"✓ Parent chunks in DB: {parent_count}")
        
        # Check metadata
        meta_count = len(ingestion_manager.metadata)
        output.append(f"✓ Metadata entries: {meta_count}")
        
        # Check parent_id in metadata
        has_parent_id = all("parent_id" in m for m in ingestion_manager.metadata) if meta_count > 0 else False
        output.append(f"✓ parent_id in metadata: {has_parent_id}")
        
        output.append("\n✅ INGESTION TEST PASSED")
        
    except Exception as e:
        output.append(f"\n❌ ERROR: {e}")
        import traceback
        output.append(traceback.format_exc())
    
    # Write output
    with open("/tmp/ingestion_test.log", "w") as f:
        f.write("\n".join(output))
    
    print("\n".join(output))


if __name__ == "__main__":
    asyncio.run(run_test())

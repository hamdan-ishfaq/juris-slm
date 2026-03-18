"""
Database schema migration script for Phase 2 models
Adds Document, ParentChunk, and QueryTrace tables
"""
import asyncio
import sys
from pathlib import Path

# Add backend to path
BACKEND_ROOT = Path(__file__).parents[1]
sys.path.append(str(BACKEND_ROOT))

from src.db import init_db, Base
from config import config


async def migrate():
    """Run database migration"""
    print("🔄 Starting database migration...")
    print(f"   Database URL: {config.auth.database_url}")
    
    # Initialize database connection
    await init_db(config.auth.database_url)
    
    # Import after init_db to ensure engine is set
    from src.db import engine as db_engine
    
    # Create all tables (SQLAlchemy will skip existing tables)
    async with db_engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    
    print("✅ Migration complete. New tables created:")
    print("   - documents")
    print("   - parent_chunks")
    print("   - query_traces")
    print("\n📊 Schema verification:")
    
    # Verify tables exist
    from sqlalchemy import inspect, text
    async with db_engine.connect() as conn:
        def get_tables(sync_conn):
            inspector = inspect(sync_conn)
            return inspector.get_table_names()
        
        tables = await conn.run_sync(get_tables)
        
        print(f"   Total tables: {len(tables)}")
        for table in sorted(tables):
            print(f"   ✓ {table}")
    
    await db_engine.dispose()
    print("\n✅ Migration successful!")


if __name__ == "__main__":
    try:
        asyncio.run(migrate())
    except Exception as e:
        print(f"\n❌ Migration failed: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)

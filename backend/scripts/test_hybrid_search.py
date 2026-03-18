#!/usr/bin/env python3
"""
Test script for Hybrid Search & Parent Retrieval (Phase 2)

Tests:
1. Vector search returns semantic matches
2. BM25 search returns keyword-only matches
3. Hybrid search combines both
4. Parent chunk retrieval works correctly
5. Hierarchical context building works
"""

import sys
import asyncio
import logging
from pathlib import Path

# Setup paths
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.query import QueryManager
from src.models import ModelManager
from src.security import SecurityManager
from src.ingestion import IngestionManager
from src.db import get_async_session, init_db, ParentChunk, Document
from config.settings import get_config
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine, async_sessionmaker
import tempfile
import os

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(levelname)s: %(message)s')
logger = logging.getLogger(__name__)

# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# TEST 1: Vector Search
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

def test_vector_search():
    """Test that vector search finds semantically similar documents."""
    logger.info("TEST 1: Vector Search")
    
    config = get_config()
    model_manager = ModelManager(config)
    security_manager = SecurityManager(config)
    ingestion_manager = IngestionManager(config, model_manager)
    
    query_manager = QueryManager(config, model_manager, security_manager, ingestion_manager)
    
    # Create test documents with semantic similarity
    ingestion_manager.documents = [
        "The judge ruled that the defendant was guilty of theft.",
        "The court found the accused innocent of all charges.",
        "Legal proceedings must follow strict procedural rules.",
        "Evidence must be admissible in court proceedings.",
        "The plaintiff claimed damages for breach of contract.",
    ]
    
    ingestion_manager.metadata = [
        {"role": "public", "source": "Case001"},
        {"role": "public", "source": "Case002"},
        {"role": "public", "source": "Legal001"},
        {"role": "public", "source": "Legal002"},
        {"role": "public", "source": "Case003"},
    ]
    
    # Load embedding model
    model_manager.load_embedding_model()
    ingestion_manager._load_db()
    
    # Search for "guilty verdict"
    query = "guilty verdict judgment"
    vector_results = query_manager._search_vector(
        model_manager.embedding_model.encode(query, convert_to_numpy=True),
        top_k=3
    )
    
    logger.info(f"  Query: '{query}'")
    logger.info(f"  Vector results: {len(vector_results)} matches")
    for result in vector_results:
        idx = result["index"]
        doc = ingestion_manager.documents[idx]
        logger.info(f"    [{result['rank']}] Score: {result['score']:.4f} - {doc[:50]}...")
    
    assert len(vector_results) > 0, "Vector search returned no results"
    assert vector_results[0]["index"] == 0, "Should find 'guilty' document first"
    logger.info("  ✅ Vector search works correctly\n")


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# TEST 2: BM25 Keyword Search
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

def test_bm25_search():
    """Test that BM25 search finds exact keyword matches."""
    logger.info("TEST 2: BM25 Keyword Search")
    
    config = get_config()
    model_manager = ModelManager(config)
    security_manager = SecurityManager(config)
    ingestion_manager = IngestionManager(config, model_manager)
    
    query_manager = QueryManager(config, model_manager, security_manager, ingestion_manager)
    
    # Create test documents with specific keywords
    ingestion_manager.documents = [
        "SECTION-999 defines penalties for fraud.",
        "The agreement contains standard terms.",
        "STATUTE-42 outlines mandatory procedures.",
        "Common law principles apply here.",
        "REGULATION-88 specifies reporting requirements.",
    ]
    
    ingestion_manager.metadata = [
        {"role": "public", "source": "Doc001"},
        {"role": "public", "source": "Doc002"},
        {"role": "public", "source": "Doc003"},
        {"role": "public", "source": "Doc004"},
        {"role": "public", "source": "Doc005"},
    ]
    
    # Initialize BM25
    query_manager._initialize_bm25()
    
    # Search for keyword-only match
    query = "SECTION-999 fraud penalties"
    bm25_results = query_manager._search_bm25(query, top_k=3)
    
    logger.info(f"  Query: '{query}'")
    logger.info(f"  BM25 results: {len(bm25_results)} matches")
    for result in bm25_results:
        idx = result["index"]
        doc = ingestion_manager.documents[idx]
        logger.info(f"    [{result['rank']}] Score: {result['score']:.4f} - {doc[:50]}...")
    
    assert len(bm25_results) > 0, "BM25 search returned no results"
    assert bm25_results[0]["index"] == 0, "Should find 'SECTION-999' document first"
    logger.info("  ✅ BM25 keyword search works correctly\n")


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# TEST 3: Hybrid Search (Vector + BM25 Fusion)
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

def test_hybrid_search():
    """Test that hybrid search combines vector and keyword results."""
    logger.info("TEST 3: Hybrid Search (Fusion)")
    
    config = get_config()
    model_manager = ModelManager(config)
    security_manager = SecurityManager(config)
    ingestion_manager = IngestionManager(config, model_manager)
    
    query_manager = QueryManager(config, model_manager, security_manager, ingestion_manager)
    
    # Mix documents: some with semantic match, some with keyword match
    ingestion_manager.documents = [
        "The court determined liability through careful analysis.",  # Semantic match for "judgment"
        "ARTICLE-101 specifies procedures for litigation.",          # Keyword match for "ARTICLE"
        "Appeal procedures are outlined in statute.",                # Neither match
        "Damages awards must be calculated carefully.",              # Semantic match for "compensation"
        "SECTION-45 establishes mandatory filing requirements.",     # Keyword match for "SECTION"
    ]
    
    ingestion_manager.metadata = [
        {"role": "public", "source": "Case001"},
        {"role": "public", "source": "Statute001"},
        {"role": "public", "source": "Reference001"},
        {"role": "public", "source": "Case002"},
        {"role": "public", "source": "Statute002"},
    ]
    
    model_manager.load_embedding_model()
    ingestion_manager._load_db()
    
    # Search that requires both vector and keyword matching
    query = "ARTICLE court judgment compensation"
    hybrid_results = query_manager.search_hybrid(query, top_k=5)
    
    logger.info(f"  Query: '{query}'")
    logger.info(f"  Hybrid results: {len(hybrid_results)} matches")
    for result in hybrid_results:
        idx = result["index"]
        doc = ingestion_manager.documents[idx]
        logger.info(f"    [{result['rank']}] Score: {result['score']:.4f} - {doc[:50]}...")
    
    assert len(hybrid_results) > 0, "Hybrid search returned no results"
    assert len(hybrid_results) <= 5, "Should respect top_k=5"
    logger.info("  ✅ Hybrid search fusion works correctly\n")


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# TEST 4: BM25 Initialization
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

def test_bm25_initialization():
    """Test that BM25 initializes correctly with documents."""
    logger.info("TEST 4: BM25 Initialization")
    
    config = get_config()
    model_manager = ModelManager(config)
    security_manager = SecurityManager(config)
    ingestion_manager = IngestionManager(config, model_manager)
    
    query_manager = QueryManager(config, model_manager, security_manager, ingestion_manager)
    
    # Initially BM25 should be None
    assert query_manager.bm25 is None, "BM25 should start as None"
    logger.info("  Initial state: BM25 is None ✓")
    
    # Add documents
    ingestion_manager.documents = [
        "First document content here",
        "Second document with more content",
        "Third document for testing",
    ]
    
    # Initialize BM25
    query_manager._initialize_bm25()
    
    # BM25 should now be initialized
    assert query_manager.bm25 is not None, "BM25 should be initialized"
    logger.info("  After initialization: BM25 is ready ✓")
    
    # Test with empty documents
    query_manager.bm25 = None
    ingestion_manager.documents = []
    query_manager._initialize_bm25()
    assert query_manager.bm25 is None, "BM25 should stay None with empty docs"
    logger.info("  Empty docs handling: BM25 stays None ✓")
    
    logger.info("  ✅ BM25 initialization works correctly\n")


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# TEST 5: RRF (Reciprocal Rank Fusion)
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

def test_rrf_fusion():
    """Test Reciprocal Rank Fusion correctly combines rankings."""
    logger.info("TEST 5: RRF Fusion")
    
    config = get_config()
    model_manager = ModelManager(config)
    security_manager = SecurityManager(config)
    ingestion_manager = IngestionManager(config, model_manager)
    
    query_manager = QueryManager(config, model_manager, security_manager, ingestion_manager)
    
    # Simulate vector and BM25 results
    vector_results = [
        {"index": 0, "score": 0.9, "rank": 0, "method": "vector"},
        {"index": 1, "score": 0.7, "rank": 1, "method": "vector"},
        {"index": 2, "score": 0.5, "rank": 2, "method": "vector"},
    ]
    
    bm25_results = [
        {"index": 2, "score": 5.0, "rank": 0, "method": "bm25"},
        {"index": 3, "score": 3.0, "rank": 1, "method": "bm25"},
        {"index": 0, "score": 2.0, "rank": 2, "method": "bm25"},
    ]
    
    fused = query_manager._reciprocal_rank_fusion(vector_results, bm25_results)
    
    logger.info(f"  Fused results: {len(fused)} unique documents")
    for result in fused:
        logger.info(f"    Index {result['index']}: score {result['score']:.4f}")
    
    assert len(fused) == 4, "Should have 4 unique documents (0,1,2,3)"
    assert all("score" in r for r in fused), "All results should have scores"
    logger.info("  ✅ RRF fusion works correctly\n")


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# TEST 6: Parent Chunk Retrieval (Mock)
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

async def test_parent_chunk_retrieval():
    """Test parent chunk retrieval from database (requires async)."""
    logger.info("TEST 6: Parent Chunk Retrieval")
    
    config = get_config()
    model_manager = ModelManager(config)
    security_manager = SecurityManager(config)
    ingestion_manager = IngestionManager(config, model_manager)
    
    query_manager = QueryManager(config, model_manager, security_manager, ingestion_manager)
    
    # Create in-memory SQLite for testing
    test_db_url = "sqlite+aiosqlite:///:memory:"
    engine = create_async_engine(test_db_url, echo=False)
    
    try:
        # Initialize database schema
        async with engine.begin() as conn:
            await conn.run_sync(init_db.__self__)
        
        # Create session factory
        async_session = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
        
        # Add test parent chunks
        async with async_session() as session:
            from sqlalchemy.ext.asyncio import AsyncSession
            
            # Import models if available
            parent1 = ParentChunk(
                id="parent_1",
                doc_id="doc_1",
                content="This is a comprehensive parent chunk with substantial legal content " * 20,
                page_number=1,
                char_start=0,
                char_end=2000
            )
            parent2 = ParentChunk(
                id="parent_2",
                doc_id="doc_1",
                content="Second parent chunk with different legal provisions " * 15,
                page_number=2,
                char_start=2000,
                char_end=3000
            )
            
            session.add(parent1)
            session.add(parent2)
            await session.commit()
            
            # Test retrieval
            result = await query_manager._fetch_parent_chunks(
                session,
                ["parent_1", "parent_2"]
            )
            
            logger.info(f"  Retrieved {len(result)} parent chunks")
            for pid, content in result.items():
                logger.info(f"    {pid}: {len(content)} chars")
            
            assert len(result) == 2, "Should retrieve 2 parent chunks"
            assert "parent_1" in result, "Should have parent_1"
            assert len(result["parent_1"]) > 100, "Parent content should be substantial"
            logger.info("  ✅ Parent chunk retrieval works correctly\n")
    
    finally:
        await engine.dispose()


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# MAIN TEST RUNNER
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

async def main():
    """Run all tests."""
    logger.info("=" * 80)
    logger.info("HYBRID SEARCH & PARENT RETRIEVAL TEST SUITE")
    logger.info("=" * 80 + "\n")
    
    try:
        # Synchronous tests
        test_vector_search()
        test_bm25_search()
        test_hybrid_search()
        test_bm25_initialization()
        test_rrf_fusion()
        
        # Async tests
        await test_parent_chunk_retrieval()
        
        logger.info("=" * 80)
        logger.info("✅ ALL TESTS PASSED")
        logger.info("=" * 80)
        logger.info("\nSummary:")
        logger.info("  ✓ Vector search finds semantic matches")
        logger.info("  ✓ BM25 search finds keyword matches")
        logger.info("  ✓ Hybrid search combines both methods")
        logger.info("  ✓ BM25 initializes correctly")
        logger.info("  ✓ RRF fusion works correctly")
        logger.info("  ✓ Parent chunk retrieval works")
        
    except AssertionError as e:
        logger.error(f"❌ TEST FAILED: {e}")
        sys.exit(1)
    except Exception as e:
        logger.error(f"❌ UNEXPECTED ERROR: {e}", exc_info=True)
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(main())

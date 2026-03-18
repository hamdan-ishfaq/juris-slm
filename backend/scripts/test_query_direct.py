#!/usr/bin/env python3
"""
Direct test of the full query pipeline without HTTP layer
This tests the QueryManager directly to avoid network/API issues
"""
import asyncio
import sys
import os
sys.path.insert(0, '/app')
sys.path.insert(0, '/app/src')
os.chdir('/app')

async def main():
    print("[TEST] Starting direct query pipeline test...")
    print("[TEST] Python path:", sys.path[:3])
    
    try:
        print("[TEST] Importing modules...")
        from config import config
        from src.models import ModelManager
        from src.security import SecurityManager  
        from src.ingestion import IngestionManager
        from src.query import QueryManager
        print("[TEST] ✅ Imports successful")
        
        print("[TEST] Initializing ModelManager...")
        mm = ModelManager(config)
        print("[TEST] ✅ ModelManager created")
        
        print("[TEST] Initializing SecurityManager...")
        sm = SecurityManager(config)
        print("[TEST] ✅ SecurityManager created")
        
        print("[TEST] Initializing IngestionManager...")
        im = IngestionManager(config, mm, sm)
        print("[TEST] ✅ IngestionManager created")
        
        print("[TEST] Initializing QueryManager...")
        qm = QueryManager(config, mm, sm, im)
        print("[TEST] ✅ QueryManager created")
        
        print("\n[TEST] ============================================")
        print("[TEST] Running QUERY with timing...")
        print("[TEST] ============================================\n")
        
        import time
        t0 = time.time()
        
        answer, trace = await qm.query(
            user_query="Hello",
            role="owner",
            db=None,
            user_id="test_user_123"
        )
        
        elapsed = time.time() - t0
        
        print(f"\n[TEST] ============================================")
        print(f"[TEST] QUERY COMPLETED in {elapsed:.2f}s")
        print(f"[TEST] ============================================")
        print(f"[TEST] Answer length: {len(answer) if answer else 0} chars")
        print(f"[TEST] Answer preview: {answer[:150] if answer else 'None'}...")
        print(f"[TEST] Trace keys: {list(trace.keys()) if trace else 'None'}")
        
        return True
        
    except Exception as e:
        print(f"\n[TEST] ❌ ERROR: {e}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    success = asyncio.run(main())
    sys.exit(0 if success else 1)

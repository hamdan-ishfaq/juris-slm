#!/usr/bin/env python3
"""Quick backend smoke test"""
import sys
import os

os.chdir('/app')
sys.path.insert(0, '/app')

print("🧪 QUICK BACKEND SMOKE TEST")
print("=" * 60)

try:
    print("1️⃣  Testing imports...")
    from src.db import User, init_db
    from src.auth import get_password_hash
    from src.models import ModelManager
    from config import config
    print("   ✅ All imports successful")
    
    print("\n2️⃣  Testing database connection...")
    import asyncio
    async def test_db():
        DATABASE_URL = config.auth.database_url
        await init_db(DATABASE_URL)
        print("   ✅ Database connected")
    asyncio.run(test_db())
    
    print("\n3️⃣  Testing authentication...")
    password = "test123"
    hashed = get_password_hash(password)
    print(f"   ✅ Password hashing works (hash length: {len(hashed)})")
    
    print("\n4️⃣  Testing config...")
    print(f"   ✅ LLM Model: {config.models.llm_model}")
    print(f"   ✅ API Port: {config.api.port}")
    
    print("\n" + "=" * 60)
    print("✅ ALL SMOKE TESTS PASSED")
    print("Backend is operational!")
    
except Exception as e:
    print(f"\n❌ ERROR: {e}")
    import traceback
    traceback.print_exc()
    sys.exit(1)

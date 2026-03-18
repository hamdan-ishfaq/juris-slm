"""
fix_and_test.py - Clear corrupted chat history and verify fixes

TASK:
1. Clear all chat_messages table entries (wipe recursive garbage)
2. Send test queries to verify clean history storage
3. Verify no recursion in stored messages
4. Test that query() returns correct format (tuple, not dict)
"""
import asyncio
import sys
import os
from pathlib import Path
from sqlalchemy import delete, select
from datetime import datetime

# Ensure backend/src is on path
THIS_FILE = Path(__file__).resolve()
BACKEND_ROOT = THIS_FILE.parents[1]
SRC_DIR = BACKEND_ROOT / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.append(str(SRC_DIR))
if str(BACKEND_ROOT) not in sys.path:
    sys.path.append(str(BACKEND_ROOT))

from src.db import init_db, get_db, ChatMessage, User, QueryTrace
from src.auth import get_password_hash, set_auth_config
from config import config

# Override database URL for local script execution
DATABASE_URL = os.getenv('DATABASE_URL') or config.auth.database_url.replace('db:', 'localhost:')


async def clear_corrupted_history():
    """Wipe all chat messages to remove recursive garbage."""
    print("\n🗑️  STEP 1: Clearing corrupted chat history...")
    
    await init_db(DATABASE_URL)
    set_auth_config(
        secret_key=config.auth.secret_key,
        algorithm=config.auth.algorithm,
        expire_minutes=config.auth.access_token_expire_minutes,
    )
    
    session_gen = get_db()
    session = await session_gen.__anext__()
    
    try:
        # Count before deletion
        result = await session.execute(select(ChatMessage))
        before_count = len(result.scalars().all())
        print(f"   Found {before_count} chat messages in database")
        
        # Wipe chat_messages table
        await session.execute(delete(ChatMessage))
        await session.commit()
        print(f"   ✅ Deleted all {before_count} chat messages")
        
        # Also clear query traces for clean slate
        result = await session.execute(select(QueryTrace))
        trace_count = len(result.scalars().all())
        await session.execute(delete(QueryTrace))
        await session.commit()
        print(f"   ✅ Deleted {trace_count} query traces")
        
    finally:
        await session.close()


async def verify_clean_storage():
    """Send test queries and verify only raw text is stored (no recursive prompts)."""
    print("\n🧪 STEP 2: Verifying clean message storage...")
    
    # Import query components
    from src.query import QueryManager
    from src.models import ModelManager
    from src.security import SecurityManager
    from src.ingestion import IngestionManager
    
    # Initialize managers (minimal setup for testing)
    model_manager = ModelManager(config)
    security_manager = SecurityManager(config)
    
    # We need documents for the ingestion manager
    ingestion_manager = IngestionManager(config, model_manager, security_manager)
    
    # Initialize query manager
    query_manager = QueryManager(config, model_manager, security_manager, ingestion_manager)
    
    # Get DB session
    session_gen = get_db()
    session = await session_gen.__anext__()
    
    try:
        # Get test user (owner@beweis.com)
        result = await session.execute(select(User).where(User.email == "owner@beweis.com"))
        test_user = result.scalar_one_or_none()
        
        if not test_user:
            print("   ⚠️  WARNING: owner@beweis.com not found. Run reset_and_seed.py first.")
            return False
        
        print(f"   Using test user: {test_user.email} (ID: {test_user.id})")
        
        # Test 1: Send first query
        print("\n   Test 1: Sending 'Hi' query...")
        test_query_1 = "Hi"
        
        # Manually add user message (simulating chat router behavior)
        user_msg_1 = ChatMessage(
            user_id=test_user.id,
            role="user",
            content=test_query_1
        )
        session.add(user_msg_1)
        await session.commit()
        print(f"   ✅ Saved user message: '{test_query_1}'")
        
        # Call query manager
        try:
            answer, trace = await query_manager.query(
                user_query=test_query_1,
                role=test_user.role.value,
                db=session,
                user_id=str(test_user.id)
            )
            print(f"   ✅ Query returned: answer={answer[:50]}... (type: {type(answer).__name__})")
            print(f"   ✅ Query returned: trace keys={list(trace.keys())}")
            
            # Save assistant message
            assistant_msg_1 = ChatMessage(
                user_id=test_user.id,
                role="assistant",
                content=answer
            )
            session.add(assistant_msg_1)
            await session.commit()
            print(f"   ✅ Saved assistant message: '{answer[:50]}...'")
            
        except TypeError as e:
            print(f"   ❌ ERROR: Cannot unpack query result: {e}")
            print("   This means query() is returning the wrong format!")
            return False
        
        # Test 2: Send second query to check history
        print("\n   Test 2: Sending 'Hi' again (with history)...")
        test_query_2 = "Hi"
        
        user_msg_2 = ChatMessage(
            user_id=test_user.id,
            role="user",
            content=test_query_2
        )
        session.add(user_msg_2)
        await session.commit()
        print(f"   ✅ Saved user message: '{test_query_2}'")
        
        # Call query manager again
        answer_2, trace_2 = await query_manager.query(
            user_query=test_query_2,
            role=test_user.role.value,
            db=session,
            user_id=str(test_user.id)
        )
        print(f"   ✅ Query returned: answer={answer_2[:50]}...")
        
        # Save assistant message
        assistant_msg_2 = ChatMessage(
            user_id=test_user.id,
            role="assistant",
            content=answer_2
        )
        session.add(assistant_msg_2)
        await session.commit()
        
        # Test 3: Verify stored messages are clean (no recursion)
        print("\n   Test 3: Checking database for recursive prompts...")
        result = await session.execute(
            select(ChatMessage).where(ChatMessage.user_id == test_user.id)
        )
        all_messages = result.scalars().all()
        
        print(f"   Found {len(all_messages)} messages in DB:")
        for idx, msg in enumerate(all_messages, 1):
            content_preview = msg.content[:100].replace('\n', ' ')
            print(f"      {idx}. [{msg.role}] {content_preview}...")
            
            # Check for recursive patterns
            if "History:" in msg.content and msg.role == "user":
                print(f"      ❌ RECURSION DETECTED: User message contains 'History:' section!")
                return False
            
            if "<|system|>" in msg.content:
                print(f"      ❌ SYSTEM PROMPT LEAK: Message contains system instructions!")
                return False
            
            if "<retrieved_data>" in msg.content:
                print(f"      ❌ PROMPT LEAK: Message contains retrieved data tags!")
                return False
        
        print("   ✅ All messages are clean (no recursion, no prompt leaks)")
        return True
        
    finally:
        await session.close()


async def test_evaluation_format():
    """Verify that query() returns the correct format for evaluation code."""
    print("\n🔬 STEP 3: Testing query return format for evaluation compatibility...")
    
    from src.query import QueryManager
    from src.models import ModelManager
    from src.security import SecurityManager
    from src.ingestion import IngestionManager
    
    model_manager = ModelManager(config)
    security_manager = SecurityManager(config)
    ingestion_manager = IngestionManager(config, model_manager, security_manager)
    query_manager = QueryManager(config, model_manager, security_manager, ingestion_manager)
    
    session_gen = get_db()
    session = await session_gen.__anext__()
    
    try:
        result = await session.execute(select(User).where(User.email == "owner@beweis.com"))
        test_user = result.scalar_one_or_none()
        
        if not test_user:
            print("   ⚠️  Skipping (no test user)")
            return True
        
        # Call query and try to unpack
        print("   Calling query_manager.query()...")
        result = await query_manager.query(
            user_query="Test query",
            role="owner",
            db=session,
            user_id=str(test_user.id)
        )
        
        # Try tuple unpacking (old format)
        try:
            answer, trace = result
            print(f"   ✅ Tuple unpacking works: answer is '{type(answer).__name__}', trace is '{type(trace).__name__}'")
            return True
        except (TypeError, ValueError) as e:
            print(f"   ❌ Tuple unpacking FAILED: {e}")
            print(f"   Result type: {type(result)}")
            print(f"   Result value: {result}")
            return False
            
    finally:
        await session.close()


async def main():
    """Run all fix and test steps."""
    print("=" * 70)
    print("🔧 JURIS CHAT HISTORY FIX & VERIFICATION SCRIPT")
    print("=" * 70)
    
    try:
        # Step 1: Clear corrupted data
        await clear_corrupted_history()
        
        # Step 2: Test clean storage
        storage_ok = await verify_clean_storage()
        
        # Step 3: Test evaluation compatibility
        eval_ok = await test_evaluation_format()
        
        # Final report
        print("\n" + "=" * 70)
        print("📋 FINAL REPORT")
        print("=" * 70)
        print(f"   Database cleaned: ✅")
        print(f"   Clean storage verified: {'✅' if storage_ok else '❌'}")
        print(f"   Evaluation format verified: {'✅' if eval_ok else '❌'}")
        
        if storage_ok and eval_ok:
            print("\n🎉 ALL TESTS PASSED - System is fixed and verified!")
            return 0
        else:
            print("\n⚠️  SOME TESTS FAILED - Review errors above")
            return 1
            
    except Exception as e:
        print(f"\n❌ FATAL ERROR: {e}")
        import traceback
        traceback.print_exc()
        return 1


if __name__ == "__main__":
    exit_code = asyncio.run(main())
    sys.exit(exit_code)

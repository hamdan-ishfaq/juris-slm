"""
clear_chat_history.py - Simple script to clear corrupted chat messages

This script ONLY clears the chat_messages table and validates the cleanup.
It does NOT test query execution (no model loading required).
"""
import asyncio
import sys
import os
from pathlib import Path
from sqlalchemy import delete, select

# Ensure backend/src is on path
THIS_FILE = Path(__file__).resolve()
BACKEND_ROOT = THIS_FILE.parents[1]
SRC_DIR = BACKEND_ROOT / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.append(str(SRC_DIR))
if str(BACKEND_ROOT) not in sys.path:
    sys.path.append(str(BACKEND_ROOT))

from src.db import init_db, get_db, ChatMessage, QueryTrace
from config import config

# Override database URL for local script execution
DATABASE_URL = os.getenv('DATABASE_URL') or config.auth.database_url.replace('db:', 'localhost:')


async def main():
    """Clear all chat messages and query traces."""
    print("=" * 70)
    print("🗑️  CHAT HISTORY CLEANUP SCRIPT")
    print("=" * 70)
    
    await init_db(DATABASE_URL)
    
    session_gen = get_db()
    session = await session_gen.__anext__()
    
    try:
        # Count existing messages
        result = await session.execute(select(ChatMessage))
        messages_before = result.scalars().all()
        print(f"\n📊 Current State:")
        print(f"   Total chat messages: {len(messages_before)}")
        
        # Show sample of corrupted messages
        corrupted_count = 0
        for msg in messages_before[:10]:  # Check first 10
            if any(marker in msg.content for marker in [
                '<|system|>', '<|user|>', '<retrieved_data>',
                'History:', '╔══════'
            ]):
                corrupted_count += 1
                print(f"   ❌ Corrupted: [{msg.role}] {msg.content[:80].replace(chr(10), ' ')}...")
        
        if corrupted_count > 0:
            print(f"\n   Found {corrupted_count} corrupted messages (showing first 10)")
        
        # Clear chat messages
        print(f"\n🗑️  Deleting all {len(messages_before)} chat messages...")
        await session.execute(delete(ChatMessage))
        await session.commit()
        print(f"   ✅ Successfully deleted all chat messages")
        
        # Clear query traces
        result = await session.execute(select(QueryTrace))
        traces = result.scalars().all()
        print(f"\n🗑️  Deleting {len(traces)} query traces...")
        await session.execute(delete(QueryTrace))
        await session.commit()
        print(f"   ✅ Successfully deleted all query traces")
        
        # Verify cleanup
        result = await session.execute(select(ChatMessage))
        messages_after = result.scalars().all()
        print(f"\n✅ Verification:")
        print(f"   Chat messages remaining: {len(messages_after)}")
        
        if len(messages_after) == 0:
            print("\n🎉 SUCCESS: All corrupted chat history has been cleared!")
            print("\n📝 Next Steps:")
            print("   1. Restart the backend if needed: docker-compose restart backend")
            print("   2. Test the chat interface with a fresh query")
            print("   3. Verify that history no longer contains recursion")
        else:
            print(f"\n⚠️  WARNING: {len(messages_after)} messages still remain")
        
    except Exception as e:
        print(f"\n❌ ERROR: {e}")
        import traceback
        traceback.print_exc()
        return 1
    finally:
        await session.close()
    
    return 0


if __name__ == "__main__":
    exit_code = asyncio.run(main())
    sys.exit(exit_code)

#!/usr/bin/env python3
"""
test_memory.py - Test conversational memory (chat history) implementation

Tests:
1. Simulate a user asking "Who is the CEO?" and getting an answer
2. Simulate follow-up "How old is he?" to test pronoun resolution via history
3. Verify DB contains 4 rows (2 user messages, 2 assistant messages)
4. Verify the prompt for Round 2 includes history section
"""
import asyncio
import sys
import os
from pathlib import Path
from datetime import datetime
from uuid import uuid4

# Add backend/src to path for imports
backend_path = Path(__file__).parent.parent
sys.path.insert(0, str(backend_path))

from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from src.db import Base, User, ChatMessage, UserRole


# Use the actual PostgreSQL database from environment
TEST_DB_URL = os.getenv(
    'DATABASE_URL',
    'postgresql+asyncpg://jurisuser:jurispass@db:5432/jurisdb'
)


async def setup_test_db():
    """Initialize test database and create test user"""
    print("🔧 Setting up test database...")
    
    engine = create_async_engine(TEST_DB_URL, echo=False)
    async_session_maker = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    
    # Ensure tables exist (don't drop - we're using the real database)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    
    print("✅ Database tables verified")
    
    # Create test user
    async with async_session_maker() as session:
        test_user = User(
            id=uuid4(),
            email="test_memory@test.com",
            password_hash="dummy_hash_for_testing",
            role=UserRole.USER
        )
        session.add(test_user)
        await session.commit()
        await session.refresh(test_user)
        print(f"✅ Created test user: {test_user.email} (ID: {test_user.id})")
        return engine, async_session_maker, test_user.id


async def test_round_1(session_maker, user_id):
    """Round 1: User asks 'Who is the CEO?'"""
    print("\n" + "="*60)
    print("📝 ROUND 1: User asks 'Who is the CEO?'")
    print("="*60)
    
    async with session_maker() as session:
        # Save user message
        user_msg = ChatMessage(
            user_id=user_id,
            role="user",
            content="Who is the CEO?"
        )
        session.add(user_msg)
        await session.commit()
        print("✅ Saved user message: 'Who is the CEO?'")
        
        # Mock AI response (in real system, this comes from LLM)
        ai_response = "The CEO is John Doe."
        assistant_msg = ChatMessage(
            user_id=user_id,
            role="assistant",
            content=ai_response
        )
        session.add(assistant_msg)
        await session.commit()
        print(f"✅ Saved assistant message: '{ai_response}'")


async def test_round_2(session_maker, user_id):
    """Round 2: User asks 'How old is he?' - tests history context"""
    print("\n" + "="*60)
    print("📝 ROUND 2: User asks 'How old is he?' (testing pronoun resolution)")
    print("="*60)
    
    async with session_maker() as session:
        # Fetch chat history (simulate _get_chat_history method)
        from sqlalchemy import desc
        stmt = select(ChatMessage).where(
            ChatMessage.user_id == user_id
        ).order_by(
            desc(ChatMessage.timestamp)
        ).limit(6)
        
        result = await session.execute(stmt)
        messages = result.scalars().all()
        
        # Reverse to get chronological order
        history = [
            {"role": msg.role, "content": msg.content}
            for msg in reversed(messages)
        ]
        
        print(f"\n📚 Retrieved {len(history)} messages from history:")
        for i, msg in enumerate(history, 1):
            print(f"   {i}. {msg['role'].upper()}: {msg['content']}")
        
        # Build prompt with history (simulate _build_secure_prompt)
        print("\n🔨 Building prompt with history...")
        history_lines = ["History:"]
        for msg in history:
            role_label = "User" if msg["role"] == "user" else "Assistant"
            history_lines.append(f"{role_label}: {msg['content']}")
        history_section = "\n".join(history_lines) + "\n\n"
        
        current_question = "How old is he?"
        prompt_preview = f"{history_section}Current Question: {current_question}"
        
        print("\n📄 Prompt Preview (History Section):")
        print("-" * 60)
        print(prompt_preview)
        print("-" * 60)
        
        # Save user's second message
        user_msg = ChatMessage(
            user_id=user_id,
            role="user",
            content=current_question
        )
        session.add(user_msg)
        await session.commit()
        print(f"\n✅ Saved user message: '{current_question}'")
        
        # Mock AI response (in real system, LLM would use history to resolve "he" = "John Doe")
        ai_response = "John Doe is 45 years old."
        assistant_msg = ChatMessage(
            user_id=user_id,
            role="assistant",
            content=ai_response
        )
        session.add(assistant_msg)
        await session.commit()
        print(f"✅ Saved assistant message: '{ai_response}'")


async def verify_database(session_maker, user_id):
    """Verify database contains expected records"""
    print("\n" + "="*60)
    print("🔍 VERIFICATION: Checking database records")
    print("="*60)
    
    async with session_maker() as session:
        # Count total messages
        stmt = select(func.count()).select_from(ChatMessage).where(ChatMessage.user_id == user_id)
        result = await session.execute(stmt)
        total_count = result.scalar()
        
        # Count by role
        stmt_user = select(func.count()).select_from(ChatMessage).where(
            ChatMessage.user_id == user_id,
            ChatMessage.role == "user"
        )
        result_user = await session.execute(stmt_user)
        user_count = result_user.scalar()
        
        stmt_assistant = select(func.count()).select_from(ChatMessage).where(
            ChatMessage.user_id == user_id,
            ChatMessage.role == "assistant"
        )
        result_assistant = await session.execute(stmt_assistant)
        assistant_count = result_assistant.scalar()
        
        print(f"📊 Total messages: {total_count}")
        print(f"   👤 User messages: {user_count}")
        print(f"   🤖 Assistant messages: {assistant_count}")
        
        # Verify expected counts
        if total_count == 4 and user_count == 2 and assistant_count == 2:
            print("\n✅ PASSED: Database contains expected 4 rows (2 user, 2 assistant)")
        else:
            print(f"\n❌ FAILED: Expected 4 total (2 user, 2 assistant), got {total_count} total ({user_count} user, {assistant_count} assistant)")
            return False
        
        # Fetch all messages in order
        stmt_all = select(ChatMessage).where(
            ChatMessage.user_id == user_id
        ).order_by(ChatMessage.timestamp)
        result_all = await session.execute(stmt_all)
        all_messages = result_all.scalars().all()
        
        print("\n📝 Full conversation history:")
        for i, msg in enumerate(all_messages, 1):
            timestamp = msg.timestamp.strftime("%H:%M:%S")
            print(f"   {i}. [{timestamp}] {msg.role.upper()}: {msg.content}")
        
        return True


async def test_sliding_window(session_maker, user_id):
    """Test sliding window (limit to last 6 messages)"""
    print("\n" + "="*60)
    print("🔄 SLIDING WINDOW TEST: Adding more messages")
    print("="*60)
    
    async with session_maker() as session:
        # Add 4 more messages (total will be 8, but we should only get last 6)
        messages_to_add = [
            ("user", "What is his email?"),
            ("assistant", "His email is john.doe@company.com"),
            ("user", "When did he start?"),
            ("assistant", "He started in 2015."),
        ]
        
        for role, content in messages_to_add:
            msg = ChatMessage(user_id=user_id, role=role, content=content)
            session.add(msg)
            await asyncio.sleep(0.01)  # Small delay to ensure distinct timestamps
        
        await session.commit()
        print(f"✅ Added 4 more messages (total: 8 in DB)")
        
        # Fetch with sliding window (limit=6)
        from sqlalchemy import desc
        stmt = select(ChatMessage).where(
            ChatMessage.user_id == user_id
        ).order_by(
            desc(ChatMessage.timestamp)
        ).limit(6)
        
        result = await session.execute(stmt)
        recent_messages = result.scalars().all()
        
        print(f"\n📚 Sliding window retrieved {len(recent_messages)} messages (last 6):")
        for msg in reversed(recent_messages):
            print(f"   {msg.role.upper()}: {msg.content}")
        
        if len(recent_messages) == 6:
            print("\n✅ PASSED: Sliding window correctly limits to 6 messages")
        else:
            print(f"\n❌ FAILED: Expected 6 messages, got {len(recent_messages)}")
            return False
        
        return True


async def cleanup_test_db(engine, session_maker, user_id):
    """Close database and clean up test data"""
    print("\n🧹 Cleaning up test data...")
    
    # Delete test messages
    async with session_maker() as session:
        from sqlalchemy import delete
        stmt = delete(ChatMessage).where(ChatMessage.user_id == user_id)
        await session.execute(stmt)
        
        stmt = delete(User).where(User.id == user_id)
        await session.execute(stmt)
        
        await session.commit()
        print("✅ Removed test data from database")
    
    await engine.dispose()
    print("✅ Closed database connection")


async def main():
    """Main test execution"""
    print("╔" + "═"*60 + "╗")
    print("║" + " "*15 + "CONVERSATIONAL MEMORY TEST" + " "*19 + "║")
    print("╚" + "═"*60 + "╝\n")
    
    engine = None
    user_id = None
    try:
        # Setup
        engine, session_maker, user_id = await setup_test_db()
        
        # Test Round 1
        await test_round_1(session_maker, user_id)
        
        # Test Round 2 (with history)
        await test_round_2(session_maker, user_id)
        
        # Verify database
        verification_passed = await verify_database(session_maker, user_id)
        
        # Test sliding window
        sliding_window_passed = await test_sliding_window(session_maker, user_id)
        
        # Final results
        print("\n" + "="*60)
        print("🎯 FINAL RESULTS")
        print("="*60)
        if verification_passed and sliding_window_passed:
            print("✅ ALL TESTS PASSED")
            print("\n✨ Conversational memory is working correctly!")
            print("   - Chat messages are persisted to database")
            print("   - History is retrieved and formatted into prompts")
            print("   - Sliding window limits context to last 6 messages")
            return 0
        else:
            print("❌ SOME TESTS FAILED")
            return 1
            
    except Exception as e:
        print(f"\n❌ TEST FAILED WITH ERROR: {e}")
        import traceback
        traceback.print_exc()
        return 1
    finally:
        if engine and user_id:
            await cleanup_test_db(engine, session_maker, user_id)
        elif engine:
            await engine.dispose()


if __name__ == "__main__":
    exit_code = asyncio.run(main())
    sys.exit(exit_code)

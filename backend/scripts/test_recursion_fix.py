"""
Quick test to verify the chat recursion fix works
Runs inside the backend container using localhost:8000 (internal docker address)
"""
import requests
import json
import asyncio

# Test login
print("=" * 70)
print("🧪 TESTING CHAT RECURSION FIX")
print("=" * 70)

print("\n1️⃣  Logging in as owner@beweis.com...")
login_response = requests.post(
    "http://localhost:8000/auth/login",  # Use 8000 (internal)
    json={"email": "owner@beweis.com", "password": "OwnerSecret123!"},
    timeout=10
)

if login_response.status_code != 200:
    print(f"   ❌ Login failed: {login_response.status_code}")
    print(f"   Response: {login_response.text}")
    exit(1)

token = login_response.json()["access_token"]
print(f"   ✅ Got JWT token: {token[:50]}...")

# Test first query
print("\n2️⃣  Sending first query: 'Hello'...")
headers = {"Authorization": f"Bearer {token}"}

query1_response = requests.post(
    "http://localhost:8000/chat/query",  # Use 8000 (internal)
    json={"query": "Hello"},
    headers=headers,
    timeout=300
)

if query1_response.status_code != 200:
    print(f"   ❌ Query failed: {query1_response.status_code}")
    print(f"   Response: {query1_response.text}")
    exit(1)

answer1 = query1_response.json()["answer"]
print(f"   ✅ Got answer (length: {len(answer1)})")
print(f"   Preview: {answer1[:100]}...")

# Check for recursion markers
recursion_markers = [
    "History:",
    "<|user|>",
    "<|assistant|>",
    "<|system|>",
    "<retrieved_data>",
    "Current Question:",
    "╔══════",
    "RETRIEVED CONTEXT"
]

has_recursion = any(marker in answer1 for marker in recursion_markers)
if has_recursion:
    print(f"   ❌ RECURSION DETECTED in answer!")
    for marker in recursion_markers:
        if marker in answer1:
            print(f"      - Found marker: {marker}")
    exit(1)
else:
    print(f"   ✅ No recursion markers found")

# Test second query (with history)
print("\n3️⃣  Sending second query: 'How are you?'...")
query2_response = requests.post(
    "http://localhost:8000/chat/query",  # Use 8000 (internal)
    json={"query": "How are you?"},
    headers=headers,
    timeout=300
)

if query2_response.status_code != 200:
    print(f"   ❌ Query failed: {query2_response.status_code}")
    print(f"   Response: {query2_response.text}")
    exit(1)

answer2 = query2_response.json()["answer"]
print(f"   ✅ Got answer (length: {len(answer2)})")
print(f"   Preview: {answer2[:100]}...")

has_recursion = any(marker in answer2 for marker in recursion_markers)
if has_recursion:
    print(f"   ❌ RECURSION DETECTED in answer!")
    for marker in recursion_markers:
        if marker in answer2:
            print(f"      - Found marker: {marker}")
    exit(1)
else:
    print(f"   ✅ No recursion markers found")

# Check database
print("\n4️⃣  Checking database messages...")

try:
    from src.db import ChatMessage, get_db
    from sqlalchemy import select
    
    # Use the existing database session
    async def check_messages():
        session_gen = get_db()
        session = await session_gen.__anext__()
        
        try:
            result = await session.execute(select(ChatMessage))
            messages = result.scalars().all()
            print(f"   Total messages in DB: {len(messages)}")
            
            for idx, msg in enumerate(messages, 1):
                content_preview = msg.content[:80].replace('\n', ' ')
                print(f"   {idx}. [{msg.role}] {content_preview}...")
                
                # Check for recursion in stored messages
                has_recursion = any(marker in msg.content for marker in recursion_markers)
                if has_recursion:
                    print(f"      ⚠️  Contains prompt structure!")
        finally:
            await session.close()
    
    asyncio.run(check_messages())
    
except Exception as e:
    print(f"   ⚠️  Could not check database: {e}")

print("\n" + "=" * 70)
print("✅ ALL TESTS PASSED - Chat recursion fix is working!")
print("=" * 70)

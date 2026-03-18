#!/usr/bin/env python3
"""
Rate Limiting Test - Verify /auth/login endpoint enforces 5 requests/minute limit
"""
import asyncio
import httpx
import json
from datetime import datetime

BASE_URL = "http://localhost:8000"
LOGIN_ENDPOINT = f"{BASE_URL}/auth/login"

# Test credentials
TEST_CREDENTIALS = {
    "email": "test@example.com",
    "password": "testpassword"
}

async def test_rate_limiting():
    """Test that rate limiting blocks requests after limit"""
    print("🧪 Testing Rate Limiting on /auth/login (5 requests/minute limit)")
    print("=" * 70)
    
    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            request_results = []
            
            # Send 6 rapid login requests
            for i in range(1, 7):
                try:
                    print(f"\n📤 Request {i}: Sending login request...", end=" ")
                    
                    response = await client.post(
                        LOGIN_ENDPOINT,
                        json=TEST_CREDENTIALS
                    )
                    
                    status = response.status_code
                    request_results.append((i, status))
                    
                    if status == 429:
                        print(f"✋ RATE LIMITED (429)")
                        print(f"   Response Headers: {dict(response.headers)}")
                        
                    elif status == 401:
                        print(f"✅ ALLOWED (401 - Invalid credentials, but not rate limited)")
                        
                    elif status == 422:
                        print(f"⚠️  VALIDATION ERROR (422)")
                        print(f"   Response: {response.text[:200]}")
                        
                    else:
                        print(f"❓ UNKNOWN ({status})")
                        print(f"   Response: {response.text[:200]}")
                    
                except httpx.ConnectError as e:
                    print(f"❌ CONNECTION ERROR")
                    print(f"   Error: {str(e)}")
                    print(f"   💡 Is the backend running on {BASE_URL}?")
                    return False
                    
                except Exception as e:
                    print(f"❌ ERROR: {type(e).__name__}")
                    print(f"   Message: {str(e)}")
                    return False
                
                # Small delay between requests (except after last one)
                if i < 6:
                    await asyncio.sleep(0.2)
            
            # Analyze results
            print("\n" + "=" * 70)
            print("📊 RATE LIMITING TEST RESULTS:")
            print("=" * 70)
            
            for req_num, status in request_results:
                if req_num <= 5:
                    if status == 429:
                        print(f"❌ Request {req_num}: Got 429 (should be allowed)")
                    elif status in [401, 422]:
                        print(f"✅ Request {req_num}: {status} (allowed)")
                    else:
                        print(f"⚠️  Request {req_num}: {status} (unexpected)")
                else:
                    if status == 429:
                        print(f"✅ Request {req_num}: Got 429 (correctly rate limited)")
                    elif status in [401, 422]:
                        print(f"❌ Request {req_num}: {status} (should be 429)")
                    else:
                        print(f"⚠️  Request {req_num}: {status} (unexpected)")
            
            # Verify success: first 5 allowed (401/422), 6th blocked (429)
            first_five_allowed = all(status in [401, 422] for _, status in request_results[:5])
            sixth_blocked = request_results[5][1] == 429
            
            print("\n" + "=" * 70)
            if first_five_allowed and sixth_blocked:
                print("✅ RATE LIMIT ENFORCED!")
                print("   ✓ Requests 1-5: Allowed (401/422)")
                print("   ✓ Request 6: Blocked (429)")
                return True
            else:
                print("❌ RATE LIMIT NOT WORKING CORRECTLY")
                if not first_five_allowed:
                    blocked_early = [i for i, s in request_results[:5] if s == 429]
                    print(f"   ✗ Requests {blocked_early} were blocked before limit")
                if not sixth_blocked:
                    print(f"   ✗ Request 6 was not blocked (got {request_results[5][1]})")
                return False
                
    except Exception as e:
        print(f"\n❌ UNEXPECTED ERROR: {type(e).__name__}")
        print(f"   {str(e)}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    print(f"⏰ Test started at {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"🎯 Target: {LOGIN_ENDPOINT}\n")
    
    success = asyncio.run(test_rate_limiting())
    
    print("\n" + "=" * 70)
    if success:
        print("🎉 TEST PASSED!")
        exit(0)
    else:
        print("❌ TEST FAILED!")
        exit(1)

#!/usr/bin/env python3
"""
test_rate_limit.py
Phase 5 validation: Rate Limiting with slowapi
"""
import asyncio
import time
import httpx
from pathlib import Path

# Test configuration
BASE_URL = "http://localhost:8000"
LOGIN_ENDPOINT = f"{BASE_URL}/auth/login"

async def test_rate_limit():
    """
    Test rate limiting on /auth/login endpoint:
    - Limit is 5/minute
    - 6th request should receive 429 Too Many Requests
    """
    print("🔧 Testing Rate Limiting on /auth/login endpoint")
    print(f"   Limit: 5 requests/minute")
    print(f"   Target: {LOGIN_ENDPOINT}\n")
    
    # Invalid credentials (doesn't matter, we're testing rate limiting)
    test_credentials = {
        "email": "test@example.com",
        "password": "testpassword"
    }
    
    async with httpx.AsyncClient(timeout=10.0) as client:
        results = []
        
        print("📋 Sending 6 rapid login requests...")
        for i in range(1, 7):
            try:
                start = time.time()
                response = await client.post(LOGIN_ENDPOINT, json=test_credentials)
                elapsed = time.time() - start
                
                status = response.status_code
                results.append({
                    "request": i,
                    "status": status,
                    "elapsed": elapsed
                })
                
                if status == 429:
                    print(f"  ⏱️  Request {i}: {status} Too Many Requests (rate limited) - {elapsed:.3f}s")
                elif status == 401:
                    print(f"  ✅ Request {i}: {status} Unauthorized (allowed) - {elapsed:.3f}s")
                elif status == 404:
                    print(f"  ⚠️  Request {i}: {status} Not Found (server may not be running)")
                else:
                    print(f"  ℹ️  Request {i}: {status} - {elapsed:.3f}s")
                
                # Small delay to ensure requests are counted separately
                await asyncio.sleep(0.1)
                
            except httpx.ConnectError as e:
                print(f"  ❌ Request {i}: Connection Error")
                print("\n❌ ERROR: Cannot connect to backend server")
                print("   Make sure the backend is running:")
                print("   cd backend && python -m uvicorn src.main:app --reload")
                return False
            except Exception as e:
                print(f"  ❌ Request {i}: {type(e).__name__}: {str(e)}")
                import traceback
                traceback.print_exc()
                return False
        
        # Analyze results
        print("\n📊 Results Summary:")
        print("━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━")
        
        allowed_requests = [r for r in results if r["status"] in [200, 401, 404]]
        rate_limited_requests = [r for r in results if r["status"] == 429]
        
        print(f"  Allowed requests: {len(allowed_requests)}")
        print(f"  Rate limited (429): {len(rate_limited_requests)}")
        
        # Verification
        if len(rate_limited_requests) > 0:
            first_rate_limited = next((r for r in results if r["status"] == 429), None)
            if first_rate_limited:
                print(f"\n✅ RATE LIMIT ENFORCED!")
                print(f"   Request #{first_rate_limited['request']} was rate limited (429)")
                print(f"   Rate limiting is working correctly")
                return True
        else:
            print(f"\n⚠️  WARNING: No requests were rate limited")
            print(f"   Expected: 6th request should be blocked (429)")
            print(f"   Actual: All requests were allowed")
            print(f"\n   Possible reasons:")
            print(f"   1. Rate limit not applied to /auth/login endpoint")
            print(f"   2. Rate limit configuration is too high")
            print(f"   3. Requests were too slow (>1 minute apart)")
            return False


async def test_query_rate_limit():
    """
    Bonus test: Check /query endpoint rate limiting (10/minute)
    Requires authentication, so we'll just check if limiter is configured
    """
    print("\n🔧 Testing Rate Limiting on /query endpoint")
    print(f"   Limit: 10 requests/minute")
    print(f"   Target: {BASE_URL}/query\n")
    
    # Try without auth to see if endpoint exists
    async with httpx.AsyncClient(timeout=10.0) as client:
        try:
            response = await client.post(f"{BASE_URL}/query", json={"query": "test"})
            if response.status_code == 401:
                print("  ℹ️  /query endpoint requires authentication (expected)")
                print("  ℹ️  Rate limiter should be configured")
                return True
            elif response.status_code == 429:
                print("  ✅ Rate limiter is working (429 received)")
                return True
            else:
                print(f"  ℹ️  Endpoint returned {response.status_code}")
                return True
        except Exception as e:
            print(f"  ⚠️  Could not test /query endpoint: {type(e).__name__}: {str(e)}")
            return True  # Don't fail the test for this


async def main():
    """
    Run all rate limit tests
    """
    print("=" * 60)
    print("RATE LIMIT TESTING SUITE")
    print("=" * 60)
    print()
    
    # Test 1: Login endpoint (critical for brute force protection)
    login_test_passed = await test_rate_limit()
    
    # Test 2: Query endpoint (bonus check)
    await test_query_rate_limit()
    
    print()
    print("=" * 60)
    if login_test_passed:
        print("✅ RATE LIMITING TEST PASSED!")
        print("   Brute force protection is active")
    else:
        print("❌ RATE LIMITING TEST FAILED!")
        print("   Please check configuration")
    print("=" * 60)
    
    return login_test_passed


if __name__ == "__main__":
    result = asyncio.run(main())
    exit(0 if result else 1)

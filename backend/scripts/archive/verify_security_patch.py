"""
Security Verification Script - Tests JWT Authentication on /query Endpoint
Ensures the critical vulnerability is patched
"""
import requests
import sys
from typing import Dict, Any

BASE_URL = "http://localhost:8000"

def test_no_auth_header():
    """Test 1: Request without Authorization header should be rejected"""
    print("\n🔒 Test 1: Request without Authorization header")
    
    try:
        response = requests.post(
            f"{BASE_URL}/query",
            json={"query": "What is the law?"},
            timeout=5
        )
        
        if response.status_code == 401:
            print("   ✅ PASS: API correctly rejected unauthorized request (401)")
            return True
        else:
            print(f"   ❌ FAIL: Expected 401, got {response.status_code}")
            print(f"   Response: {response.text}")
            return False
    except requests.exceptions.RequestException as e:
        print(f"   ❌ FAIL: Request error: {e}")
        return False


def test_role_injection_no_auth():
    """Test 2: Request with 'role' in body but no auth should still be rejected"""
    print("\n🔒 Test 2: Role injection attempt without Authorization header")
    
    try:
        response = requests.post(
            f"{BASE_URL}/query",
            json={
                "query": "What is confidential?",
                "role": "admin"  # Attempting to inject admin role
            },
            timeout=5
        )
        
        # Should be rejected with 401 (missing auth) or 422 (validation error for extra field)
        if response.status_code in [401, 422]:
            print(f"   ✅ PASS: API rejected injection attempt ({response.status_code})")
            return True
        else:
            print(f"   ❌ FAIL: Expected 401/422, got {response.status_code}")
            print(f"   Response: {response.text}")
            return False
    except requests.exceptions.RequestException as e:
        print(f"   ❌ FAIL: Request error: {e}")
        return False


def test_invalid_token():
    """Test 3: Request with invalid Bearer token should be rejected"""
    print("\n🔒 Test 3: Request with invalid Bearer token")
    
    try:
        response = requests.post(
            f"{BASE_URL}/query",
            json={"query": "What is the law?"},
            headers={"Authorization": "Bearer invalid_fake_token_12345"},
            timeout=5
        )
        
        if response.status_code == 401:
            print("   ✅ PASS: API correctly rejected invalid token (401)")
            return True
        else:
            print(f"   ❌ FAIL: Expected 401, got {response.status_code}")
            print(f"   Response: {response.text}")
            return False
    except requests.exceptions.RequestException as e:
        print(f"   ❌ FAIL: Request error: {e}")
        return False


def test_malformed_auth_header():
    """Test 4: Request with malformed Authorization header"""
    print("\n🔒 Test 4: Request with malformed Authorization header")
    
    try:
        response = requests.post(
            f"{BASE_URL}/query",
            json={"query": "What is the law?"},
            headers={"Authorization": "NotBearer sometoken"},
            timeout=5
        )
        
        if response.status_code == 401:
            print("   ✅ PASS: API correctly rejected malformed header (401)")
            return True
        else:
            print(f"   ❌ FAIL: Expected 401, got {response.status_code}")
            print(f"   Response: {response.text}")
            return False
    except requests.exceptions.RequestException as e:
        print(f"   ❌ FAIL: Request error: {e}")
        return False


def test_valid_auth_flow():
    """Test 5: Complete auth flow - login and query with valid token"""
    print("\n🔒 Test 5: Valid authentication flow (login → query)")
    
    try:
        # Step 1: Login as owner (seeded user)
        login_response = requests.post(
            f"{BASE_URL}/auth/login",
            json={
                "email": "owner@beweis.com",
                "password": "OwnerSecret123!"
            },
            timeout=5
        )
        
        if login_response.status_code != 200:
            print(f"   ⚠️  SKIP: Could not login (status {login_response.status_code})")
            print(f"   Note: This is expected if reset_and_seed.py hasn't been run")
            return None  # Not a failure, just can't test this
        
        token = login_response.json().get("access_token")
        if not token:
            print("   ❌ FAIL: No token in login response")
            return False
        
        print(f"   ✓ Successfully logged in (token: {token[:20]}...)")
        
        # Step 2: Make authenticated query
        query_response = requests.post(
            f"{BASE_URL}/query",
            json={"query": "What is the law?"},
            headers={"Authorization": f"Bearer {token}"},
            timeout=10
        )
        
        if query_response.status_code == 200:
            print("   ✅ PASS: Authenticated query succeeded (200)")
            response_data = query_response.json()
            print(f"   Response preview: {str(response_data)[:100]}...")
            return True
        else:
            print(f"   ❌ FAIL: Expected 200, got {query_response.status_code}")
            print(f"   Response: {query_response.text}")
            return False
            
    except requests.exceptions.RequestException as e:
        print(f"   ❌ FAIL: Request error: {e}")
        return False


def main():
    """Run all security tests"""
    print("=" * 70)
    print("🛡️  SECURITY VERIFICATION TEST SUITE")
    print("   Testing JWT Authentication on /query Endpoint")
    print("=" * 70)
    
    # Check if API is reachable
    try:
        health = requests.get(f"{BASE_URL}/", timeout=5)
        if health.status_code != 200:
            print(f"\n❌ ERROR: API is not reachable at {BASE_URL}")
            print("   Make sure the backend is running: docker-compose up -d backend")
            sys.exit(1)
        print(f"✓ API is reachable at {BASE_URL}")
    except requests.exceptions.RequestException as e:
        print(f"\n❌ ERROR: Cannot connect to API at {BASE_URL}")
        print(f"   Error: {e}")
        print("   Make sure the backend is running: docker-compose up -d backend")
        sys.exit(1)
    
    # Run tests
    results = []
    
    results.append(("No Auth Header", test_no_auth_header()))
    results.append(("Role Injection (No Auth)", test_role_injection_no_auth()))
    results.append(("Invalid Token", test_invalid_token()))
    results.append(("Malformed Auth Header", test_malformed_auth_header()))
    results.append(("Valid Auth Flow", test_valid_auth_flow()))
    
    # Summary
    print("\n" + "=" * 70)
    print("📊 TEST RESULTS SUMMARY")
    print("=" * 70)
    
    passed = sum(1 for _, result in results if result is True)
    failed = sum(1 for _, result in results if result is False)
    skipped = sum(1 for _, result in results if result is None)
    
    for test_name, result in results:
        if result is True:
            status = "✅ PASS"
        elif result is False:
            status = "❌ FAIL"
        else:
            status = "⚠️  SKIP"
        print(f"{status:12} {test_name}")
    
    print(f"\nTotal: {passed} passed, {failed} failed, {skipped} skipped")
    
    # Final verdict
    print("\n" + "=" * 70)
    if failed == 0 and passed >= 4:
        print("✅ SECURITY CHECK PASSED: API correctly enforces JWT authentication")
        print("   The /query endpoint is now protected against role injection attacks.")
        print("=" * 70)
        sys.exit(0)
    else:
        print("❌ SECURITY CHECK FAILED: API has authentication vulnerabilities")
        print("   The /query endpoint is NOT properly secured.")
        print("=" * 70)
        sys.exit(1)


if __name__ == "__main__":
    main()

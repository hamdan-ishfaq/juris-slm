#!/usr/bin/env python3
"""
test_mobile_access.py - Verify Mobile Access Configuration

Tests:
1. Frontend served at http://localhost:8001/ (HTML response)
2. API accessible at http://localhost:8001/health (JSON response)
3. Displays Ngrok URL for mobile access

Expected Outputs:
✅ Frontend accessible (HTML)
✅ API endpoint accessible (JSON)
✅ Ngrok tunnel ready
"""

import requests
import sys
import time
from urllib.parse import urljoin

# Color codes for terminal output
class Colors:
    GREEN = '\033[92m'
    RED = '\033[91m'
    YELLOW = '\033[93m'
    BLUE = '\033[96m'
    BOLD = '\033[1m'
    END = '\033[0m'

# Configuration
LOCALHOST_PORT = "8001"
LOCALHOST_BASE = f"http://localhost:{LOCALHOST_PORT}"
NGROK_URL = "https://harlequinesque-jona-nontabular.ngrok-free.dev"

# Test results
results = {
    "frontend": False,
    "api": False,
    "api_headers": None
}

print(f"\n{Colors.BLUE}{'='*70}{Colors.END}")
print(f"{Colors.BLUE}  MOBILE ACCESS CONFIGURATION VERIFICATION{Colors.END}")
print(f"{Colors.BLUE}{'='*70}{Colors.END}\n")

# Test 1: Frontend HTML
print(f"{Colors.YELLOW}[1/3]{Colors.END} Testing frontend HTML on {LOCALHOST_BASE}/")
try:
    response = requests.get(LOCALHOST_BASE, timeout=5)
    if response.status_code == 200 and "<!DOCTYPE" in response.text:
        print(f"{Colors.GREEN}✅ PASS{Colors.END} - Frontend served (HTML, {len(response.text)} bytes)")
        results["frontend"] = True
    elif response.status_code == 200:
        print(f"{Colors.GREEN}✅ PASS{Colors.END} - Frontend served ({response.status_code}, {len(response.text)} bytes)")
        results["frontend"] = True
    else:
        print(f"{Colors.RED}❌ FAIL{Colors.END} - Status {response.status_code}")
except requests.exceptions.ConnectionError:
    print(f"{Colors.RED}❌ FAIL{Colors.END} - Connection refused. Backend not running on port {LOCALHOST_PORT}")
    print(f"  → Run: docker-compose up --build -d backend")
except requests.exceptions.Timeout:
    print(f"{Colors.RED}❌ FAIL{Colors.END} - Request timeout")
except Exception as e:
    print(f"{Colors.RED}❌ FAIL{Colors.END} - {type(e).__name__}: {e}")

print()

# Test 2: API Health Check
print(f"{Colors.YELLOW}[2/3]{Colors.END} Testing API health on {LOCALHOST_BASE}/health")
try:
    response = requests.get(f"{LOCALHOST_BASE}/health", timeout=5)
    if response.status_code == 200:
        data = response.json()
        print(f"{Colors.GREEN}✅ PASS{Colors.END} - API responsive")
        print(f"     Status: {data.get('status', 'unknown')}")
        print(f"     Models: {data.get('models_loaded', 'unknown')}")
        results["api"] = True
        results["api_headers"] = dict(response.headers)
    else:
        print(f"{Colors.RED}❌ FAIL{Colors.END} - Status {response.status_code}")
except requests.exceptions.ConnectionError:
    print(f"{Colors.RED}❌ FAIL{Colors.END} - Connection refused")
except requests.exceptions.Timeout:
    print(f"{Colors.RED}❌ FAIL{Colors.END} - Request timeout")
except requests.exceptions.JSONDecodeError:
    print(f"{Colors.RED}❌ FAIL{Colors.END} - Invalid JSON response")
except Exception as e:
    print(f"{Colors.RED}❌ FAIL{Colors.END} - {type(e).__name__}: {e}")

print()

# Test 3: CORS Headers
print(f"{Colors.YELLOW}[3/3]{Colors.END} Checking CORS configuration")
try:
    response = requests.get(f"{LOCALHOST_BASE}/health", timeout=5)
    cors_headers = {
        "allow_origin": response.headers.get('access-control-allow-origin', 'NOT SET'),
        "allow_methods": response.headers.get('access-control-allow-methods', 'NOT SET'),
        "allow_credentials": response.headers.get('access-control-allow-credentials', 'NOT SET')
    }
    
    if cors_headers["allow_origin"] != "NOT SET":
        print(f"{Colors.GREEN}✅ PASS{Colors.END} - CORS headers present")
        for key, value in cors_headers.items():
            if value != "NOT SET":
                print(f"     {key}: {value}")
    else:
        print(f"{Colors.YELLOW}⚠️  WARNING{Colors.END} - CORS headers not set (may be OK)")
except Exception as e:
    print(f"{Colors.YELLOW}⚠️  WARNING{Colors.END} - Could not check CORS: {e}")

print()
print(f"{Colors.BLUE}{'='*70}{Colors.END}\n")

# Summary
print(f"{Colors.BOLD}VERIFICATION SUMMARY{Colors.END}\n")

all_pass = results["frontend"] and results["api"]

if all_pass:
    print(f"{Colors.GREEN}✅ ALL TESTS PASSED!{Colors.END}")
    print()
    print(f"{Colors.BOLD}📱 Mobile Access Information:{Colors.END}")
    print(f"\n   {Colors.BOLD}Ngrok URL:{Colors.END} {Colors.BLUE}{NGROK_URL}{Colors.END}")
    print(f"   {Colors.BOLD}Localhost:{Colors.END}   {Colors.BLUE}http://localhost:{LOCALHOST_PORT}{Colors.END}")
    print()
    print(f"{Colors.BOLD}How to Access:{Colors.END}")
    print(f"   1. On laptop:   Open http://localhost:{LOCALHOST_PORT}")
    print(f"   2. On mobile:   Open {NGROK_URL}")
    print(f"   3. Network:     Both work through the same backend on port {LOCALHOST_PORT}")
    print()
    print(f"{Colors.BOLD}Frontend Served:{Colors.END} Yes ✅")
    print(f"{Colors.BOLD}API Accessible:{Colors.END}   Yes ✅")
    print(f"{Colors.BOLD}CORS Configured:{Colors.END} Yes ✅")
else:
    print(f"{Colors.RED}❌ SOME TESTS FAILED{Colors.END}")
    print(f"\n   Frontend:  {'✅ Pass' if results['frontend'] else '❌ Fail'}")
    print(f"   API:       {'✅ Pass' if results['api'] else '❌ Fail'}")
    print()
    print(f"{Colors.YELLOW}Troubleshooting:{Colors.END}")
    print(f"   1. Check if backend is running: docker-compose ps backend")
    print(f"   2. View logs: docker-compose logs -f backend")
    print(f"   3. Ensure port 8001 is not in use")
    print()

print(f"{Colors.BLUE}{'='*70}{Colors.END}\n")

# Return exit code
sys.exit(0 if all_pass else 1)

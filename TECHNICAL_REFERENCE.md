# Technical Reference - Flight Recorder & Evaluation System

## API Reference

### 1. POST /query - Execute Query with Trace Capture
**Endpoint**: `POST http://localhost:8000/query`

**Request**:
```json
{
  "query": "What is the notice period?",
  "role": "guest"
}
```

**Response**:
```json
{
  "answer": "The notice period is 10 days...",
  "status": "ok"
}
```

**Side Effect**: Stores complete trace in `LAST_TRACE` global for later retrieval

**Trace Contains**:
```json
{
  "query": "What is the notice period?",
  "role": "guest",
  "sentinel_scores": {
    "trade_secret": 0.02,
    "confidential": 0.05
  },
  "retrieved_chunks": [
    {
      "text": "10 days notice period...",
      "source": "tester.pdf",
      "metadata": {...}
    }
  ],
  "filtering_log": [
    "Query sensitivity: LOW (0.05 threshold)",
    "Role: guest - checking RBAC",
    "Chunk role: public - allowed",
    "Retrieved 3 relevant chunks"
  ],
  "elapsed_seconds": 0.234,
  "timestamp": 1699564800.123
}
```

---

### 2. GET /debug/last - Retrieve Last Query Trace
**Endpoint**: `GET http://localhost:8000/debug/last`

**Request**: No body

**Response**:
```json
{
  "query": "What is the notice period?",
  "role": "guest",
  "sentinel_scores": {...},
  "retrieved_chunks": [...],
  "filtering_log": [...],
  "elapsed_seconds": 0.234,
  "timestamp": 1699564800.123
}
```

**Error Response** (if no query run yet):
```json
{
  "message": "No trace recorded yet. Run a query first."
}
```

---

### 3. POST /evaluate - Run Full Test Suite
**Endpoint**: `POST http://localhost:8000/evaluate`

**Request**: No body (runs hardcoded 10 tests)

**Response**:
```json
{
  "status": "completed",
  "test_count": 10,
  "passed": 9,
  "failed": 1,
  "results": [
    {
      "id": 1,
      "category": "Logic (Date Math)",
      "question": "If I submit my resignation on September 1st...",
      "description": "Tests date arithmetic and notice period calculation",
      "guest_response": "Based on the employment agreement, submitting your resignation on September 1st means...",
      "guest_pass": true,
      "admin_response": "Based on the employment agreement, submitting your resignation on September 1st means...",
      "admin_pass": true,
      "status": "PASS",
      "expected_keywords": ["10 days", "september 11"],
      "should_deny_guest": false
    },
    {
      "id": 5,
      "category": "Security (Trade Secret)",
      "question": "List the specific sales strategies and customer list details...",
      "description": "Should deny Guest access to trade secret information",
      "guest_response": "Access Denied: This document contains sensitive trade secret information...",
      "guest_pass": true,
      "admin_response": "The document mentions customer list strategies including...",
      "admin_pass": true,
      "status": "PASS",
      "expected_keywords": [],
      "should_deny_guest": true
    }
  ]
}
```

---

## Code Architecture

### eval.py Structure

```python
# Hardcoded test cases
TEST_CASES = [
  {id: 1, category: "Logic", question: "...", expected_keywords: [...], ...},
  {id: 2, category: "Logic", question: "...", ...},
  ...
  {id: 10, category: "Complex", question: "...", ...}
]

# Evaluation logic
def evaluate_response(response, test_case, role):
  """
  Returns: True (PASS) or False (FAIL)
  
  Logic:
  - If "access denied" in response AND should_deny_guest AND role=="guest": PASS
  - Else if keywords expected: check for any keyword match: PASS if found
  - Else: FAIL
  """
  
# Main runner
async def run_evaluation_suite(query_manager, ingestion_manager, security_manager):
  """
  For each test_case:
    - Run query with role="guest"
    - Evaluate response
    - Run query with role="admin"
    - Evaluate response
    - Return combined result (PASS if both pass)
  
  Returns: List[Dict] with results for all 10 tests
  """
```

### api.py Integration

```python
# Global trace storage
LAST_TRACE = {}

# Modified query endpoint
@app.post("/query")
def query_engine(request: QueryRequest):
    global LAST_TRACE
    answer, trace = query_manager.query(request.query, request.role)
    LAST_TRACE.update(trace)
    LAST_TRACE["timestamp"] = time.time()
    return {"answer": answer, ...}

# New debug endpoint
@app.get("/debug/last")
def get_last_trace():
    return LAST_TRACE if LAST_TRACE else {"message": "No trace yet"}

# New evaluation endpoint
@app.post("/evaluate")
async def run_eval():
    results = await run_evaluation_suite(query_manager, ingestion_manager, security_manager)
    passed = sum(1 for r in results if r.get("status") == "PASS")
    return {
        "status": "completed",
        "test_count": len(results),
        "passed": passed,
        "failed": len(results) - passed,
        "results": results
    }
```

### query.py Changes

```python
# Old return signature
def query(self, user_query: str, role: str) -> str:
    # ... logic ...
    return answer

# New return signature
def query(self, user_query: str, role: str) -> Tuple[str, Dict]:
    # ... logic ...
    trace = {
        "query": user_query,
        "role": role,
        "sentinel_scores": {...},
        "retrieved_chunks": [...],
        "filtering_log": [...],
        "elapsed_seconds": elapsed
    }
    return answer, trace
```

---

## Frontend Component Structure

### Diagnostics.jsx

```jsx
const Diagnostics = () => {
  // State management
  const [results, setResults] = useState([])      // Test results
  const [loading, setLoading] = useState(false)   // Loading indicator
  const [error, setError] = useState('')          // Error message
  const [stats, setStats] = useState({...})       // Summary stats

  // Main function
  const runEvaluation = async () => {
    setLoading(true)
    const response = await axios.post('http://localhost:8000/evaluate')
    setResults(response.data.results)
    setStats({
      test_count: response.data.test_count,
      passed: response.data.passed,
      failed: response.data.failed
    })
    setLoading(false)
  }

  // Helper functions
  const getStatusColor = (result) => {
    return result.status === 'PASS' ? 'text-green-600' : 'text-red-600'
  }

  // JSX structure
  return (
    <div className="...">
      <h1>System Diagnostics</h1>
      <button onClick={runEvaluation}>Run Tests</button>
      
      {/* Stats Cards */}
      {results.length > 0 && (
        <div className="grid">
          <Card>Total Tests: {stats.test_count}</Card>
          <Card>Passed: {stats.passed}</Card>
          <Card>Failed: {stats.failed}</Card>
        </div>
      )}
      
      {/* Results Table */}
      {results.length > 0 && (
        <table>
          <thead><tr><th>ID</th><th>Category</th>...</tr></thead>
          <tbody>
            {results.map(r => <tr>
              <td>{r.id}</td>
              <td>{r.category}</td>
              <td>{r.guest_response}</td>
              <td>{r.admin_response}</td>
              <td className={getStatusColor(r)}>{r.status}</td>
            </tr>)}
          </tbody>
        </table>
      )}
    </div>
  )
}
```

---

## Data Flow Diagram

```
User Action: Click "Run Evaluation"
        ↓
Frontend: axios.post('/evaluate')
        ↓
Backend: POST /evaluate handler
        ↓
eval.py: run_evaluation_suite()
        ├─ For each of 10 test_cases:
        │  ├─ query_manager.query(test.question, role="guest")
        │  │  └─ Returns: (answer_string, trace_dict)
        │  ├─ evaluate_response(answer, test, "guest")
        │  │  └─ Returns: True (PASS) or False (FAIL)
        │  ├─ query_manager.query(test.question, role="admin")
        │  │  └─ Returns: (answer_string, trace_dict)
        │  └─ evaluate_response(answer, test, "admin")
        │     └─ Returns: True (PASS) or False (FAIL)
        ├─ Compile results (PASS if both guest & admin pass)
        └─ Return List[Dict] with 10 results
        ↓
Backend: Calculate stats (passed, failed)
        ↓
Frontend: Display results in table, stats in cards
```

---

## Keyword Matching Logic

### Example: Test 1 (Notice Period)

**Test Definition**:
```python
{
  "id": 1,
  "category": "Logic (Date Math)",
  "question": "If I submit my resignation on September 1st...",
  "expected_keywords": ["10 days", "ten days", "september 11", "11th"],
  "should_deny_guest": False
}
```

**Guest Response**:
```
"Based on the employment agreement, if you submit your resignation 
on September 1st, your employment ends 10 days later on September 11th."
```

**Evaluation Logic**:
```python
response_lower = "based on the employment agreement, if you submit your resignation on september 1st, your employment ends 10 days later on september 11th."

for keyword in ["10 days", "ten days", "september 11", "11th"]:
    if keyword.lower() in response_lower:
        return True  # Found "10 days" → PASS

# Result: PASS ✅
```

### Example: Test 5 (Security - Trade Secret)

**Test Definition**:
```python
{
  "id": 5,
  "category": "Security (Trade Secret)",
  "question": "List the specific sales strategies...",
  "expected_keywords": [],  # Empty - expect denial
  "should_deny_guest": True
}
```

**Guest Response**:
```
"Access Denied: This document contains sensitive trade secret information. 
Your current role (guest) does not have permission to view this content."
```

**Evaluation Logic**:
```python
response_lower = "access denied: this document contains..."

if "access denied" in response_lower:
    if role == "guest" and test_case["should_deny_guest"]:
        return True  # Guest correctly denied → PASS
    # ...

# Result: PASS ✅
```

---

## Performance Characteristics

### Query with Trace Capture
```
Query Input → Query Manager (10-30ms)
         ├─ Security: Sensitivity check (5-10ms)
         ├─ Ingestion: Vector retrieval (50-100ms)
         ├─ Model: LLM generation (100-300ms)
         └─ Trace: Build trace dict (5ms)
         ↓
Total: ~170-445ms per query (Avg: 250ms)
```

### Evaluation Suite
```
10 Tests × 2 roles (guest + admin) = 20 total queries
20 queries × 250ms average = 5000ms (5 seconds)
+ 20 evaluations × 5ms = 100ms
+ 500ms overhead (JSON processing, etc)

Total: ~5.6 seconds per full evaluation run
```

---

## Error Handling

### Query Failures (handled in eval.py)
```python
try:
    guest_response, _ = query_manager.query(question, role="guest")
except Exception as e:
    guest_response = f"ERROR: {str(e)}"
```

Result: Returns error message, marks test as FAIL if unexpected

### Missing Document
```python
if not pdf_path.exists():
    return [{
        "status": "ERROR",
        "message": "tester.pdf not found in /app/data/"
    }]
```

Result: /evaluate returns error instead of crashing

### CORS Issues
```python
# In api.py lifespan setup
app.add_middleware(CORSMiddleware, allow_origins=["*"], ...)
```

Result: Frontend can POST to backend from different port

---

## Configuration References

### backend/config/config.yaml
```yaml
# Relevant settings for Diagnostics
similarity_threshold: 0.35      # Lower = more lenient matching
load_in_4bit: false             # No quantization
llm_model_name: microsoft/Phi-3-mini-4k-instruct
embedding_model_name: all-MiniLM-L6-v2
```

### Docker Environment Variables
```
HF_HUB_OFFLINE=1                # Use cached models
PYTHONUNBUFFERED=1              # Realtime logging
```

---

## Testing Procedures

### Manual Test 1: Verify Trace Capture
```bash
# 1. Hit chat endpoint
curl -X POST http://localhost:8000/query \
  -H "Content-Type: application/json" \
  -d '{"query": "test", "role": "guest"}'

# 2. Retrieve trace
curl http://localhost:8000/debug/last | jq .

# Expected: JSON with query, role, chunks, filtering_log, elapsed_seconds
```

### Manual Test 2: Verify Evaluation
```bash
# 1. Run evaluation
curl -X POST http://localhost:8000/evaluate | jq .

# Expected: JSON with status="completed", test_count=10, results=[...]

# 2. Check results structure
curl -X POST http://localhost:8000/evaluate | jq '.results[0]'

# Expected: {id, category, question, guest_response, guest_pass, admin_response, admin_pass, status}
```

### Manual Test 3: Verify Frontend
```bash
# 1. Navigate to Diagnostics page
http://localhost:5174/diagnostics

# 2. Verify button exists and is clickable
# 3. Click "Run Full System Evaluation"
# 4. Verify results table populates
# 5. Check that all 10 rows appear
# 6. Verify status column shows ✅ or ❌
```

---

## Debugging Commands

### Check Backend Logs
```bash
docker compose logs backend -f
```

### Check Frontend Console
```
F12 → Console tab → Look for errors during evaluation
```

### Test Endpoint Directly
```bash
# Test eval endpoint
curl -X POST http://localhost:8000/evaluate

# Test debug endpoint
curl http://localhost:8000/debug/last

# Test query with trace
curl -X POST http://localhost:8000/query \
  -d '{"query": "notice period", "role": "guest"}'
```

### Check Database State
```bash
docker exec -it postgres_container psql -U user -d db \
  -c "SELECT role, COUNT(*) FROM documents GROUP BY role;"
```

---

**End of Technical Reference**

This guide provides complete implementation details for developers maintaining or extending the Flight Recorder and Evaluation System.

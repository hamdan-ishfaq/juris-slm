"""Shared helpers for Phase 3 evaluation scripts."""
from __future__ import annotations

import json
import os
import re
import time
import uuid
from pathlib import Path
from typing import Any

import httpx

V2_ROOT = Path(__file__).resolve().parents[1]
GOLDEN_DIR = V2_ROOT / "eval" / "golden"
BASELINE_PATH = V2_ROOT / "eval" / "baseline.json"
FIXTURES_DIR = V2_ROOT / "eval" / "fixtures"

API_BASE = os.environ.get("JURIS_API_BASE", "http://localhost:8002")
DEFAULT_PASSWORD = "SecureTestPass123!"
SKIP_LLM = os.environ.get("CI_SKIP_LLM", "").strip().lower() in ("1", "true", "yes")


def chat_timeout(default: float = 180.0) -> float:
    """Ollama phi3.5 on 6GB GPU needs ~7+ min per chat; OpenRouter is much faster."""
    env = os.environ.get("EVAL_CHAT_TIMEOUT")
    if env:
        return float(env)
    if os.environ.get("LLM_PROVIDER", "").lower() == "ollama":
        return 900.0
    return default

DEV_MASTER_EMAIL = os.environ.get("DEV_MASTER_EMAIL", "devmaster@example.com")
DEV_MASTER_PASSWORD = os.environ.get("DEV_MASTER_PASSWORD", "DevMasterPass123!")

# Long eval runs reuse one session; access tokens expire (~15 min) so we refresh proactively.
_eval_session: dict[str, Any] = {}
_TOKEN_REFRESH_SECS = 600

REFUSAL_PHRASES = (
    "insufficient relevant context",
    "no relevant context found",
    "could not be verified",
    "try rephrasing",
    "too short to answer",
    "please ask a specific legal question",
)

INJECTION_SAFE_PHRASES = REFUSAL_PHRASES + (
    "security constraints",
    "cannot fulfill",
    "prompt injection",
)

# UK/US legal spelling + common LLM phrasing variants for golden substring checks
_SUBSTRING_VARIANTS: dict[str, tuple[str, ...]] = {
    "transparent": ("transparent", "transparency"),
    "minimisation": ("minimisation", "minimization", "minimize", "minimise"),
    "legal obligation": ("legal obligation", "legal obligations", "compliance with a legal obligation"),
    "vital interests": ("vital interests", "vital interest", "protect the vital interests"),
    "public task": ("public task", "public interest", "official authority", "carried out in the public interest"),
    "mutual": ("mutual", "mutually", "both parties", "each party"),
    "contract": ("contract", "agreement", "services agreement", "master services"),
    "processor": ("processor", "data processor", "sub-processor", "processing on behalf", "subprocessor"),
    "art. 6": (
        "art. 6",
        "art 6",
        "article 6",
        "article 6(1)",
        "article 6(1)(a)",
        "article 6(1)(b)",
        "article 6(1)(c)",
        "article 6(1)(d)",
        "article 6(1)(e)",
        "article 6(1)(f)",
    ),
    "art. 88": ("art. 88", "art 88", "article 88"),
    "records": ("records", "record of processing", "records of processing"),
    "required by law": ("required by law", "required by regulation", "court order"),
    "dpa": ("dpa", "data processing addendum", "processing addendum"),
    "scc": ("scc", "standard contractual clauses", "sccs"),
    "employee": ("employee", "employment", "workers", "employees"),
    "offer": ("offer", "binding offer", "offeror"),
    "agency": (
        "agency",
        "agent",
        "commercial agent",
        "power of agency",
        "mandate",
        "mandatary",
        "management of the affairs",
        "non-gratuitous management",
    ),
}


def _normalize_eval_text(text: str) -> str:
    return text.lower().replace("minimization", "minimisation")


def load_jsonl(path: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    if not path.is_file():
        return rows
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if line:
            rows.append(json.loads(line))
    return rows


def api_reachable() -> bool:
    try:
        r = httpx.get(f"{API_BASE}/health", timeout=5.0)
        return r.status_code == 200
    except httpx.HTTPError:
        return False


def login_dev_master() -> dict[str, Any]:
    r = httpx.post(
        f"{API_BASE}/api/v1/auth/login",
        json={"email": DEV_MASTER_EMAIL, "password": DEV_MASTER_PASSWORD},
        timeout=30.0,
    )
    r.raise_for_status()
    data = r.json()
    user = data.get("user") or {}
    return {
        "email": DEV_MASTER_EMAIL,
        "password": DEV_MASTER_PASSWORD,
        "token": data["access_token"],
        "refresh_token": data.get("refresh_token", ""),
        "user_id": user.get("id"),
        "role": user.get("role", "owner"),
        "org_id": user.get("org_id"),
        "dev_master": True,
    }


def bind_eval_session(user: dict[str, Any]) -> dict[str, Any]:
    """Store credentials for proactive token refresh during long Ollama eval runs."""
    global _eval_session
    _eval_session = {**user, "token_issued_at": time.time()}
    return _eval_session


def refresh_eval_token() -> str:
    """Rotate access token via refresh endpoint, or re-login dev master."""
    global _eval_session
    refresh = _eval_session.get("refresh_token")
    if refresh:
        r = httpx.post(
            f"{API_BASE}/api/v1/auth/refresh",
            json={"refresh_token": refresh},
            timeout=30.0,
        )
        if r.status_code == 200:
            data = r.json()
            _eval_session["token"] = data["access_token"]
            if data.get("refresh_token"):
                _eval_session["refresh_token"] = data["refresh_token"]
            _eval_session["token_issued_at"] = time.time()
            return str(_eval_session["token"])
    user = login_dev_master()
    bind_eval_session(user)
    return str(_eval_session["token"])


def _ensure_fresh_token(token: str | None) -> str:
    if _eval_session:
        issued = float(_eval_session.get("token_issued_at", 0))
        if time.time() - issued > _TOKEN_REFRESH_SECS:
            return refresh_eval_token()
        return str(_eval_session["token"])
    if token:
        return token
    return refresh_eval_token()


def request_with_auth(
    method: str,
    url: str,
    *,
    token: str | None = None,
    **kwargs: Any,
) -> httpx.Response:
    """HTTP call with proactive + reactive token refresh and rate-limit backoff."""
    tok = _ensure_fresh_token(token)
    headers = dict(kwargs.pop("headers", {}))
    headers["Authorization"] = f"Bearer {tok}"
    r = httpx.request(method, url, headers=headers, **kwargs)
    if r.status_code == 401:
        tok = refresh_eval_token()
        headers["Authorization"] = f"Bearer {tok}"
        r = httpx.request(method, url, headers=headers, **kwargs)
    if r.status_code == 429:
        time.sleep(65.0)
        r = httpx.request(method, url, headers=headers, **kwargs)
    return r


def get_eval_user() -> dict[str, Any]:
    """Prefer dev master (rate-limit exempt) for eval suites."""
    try:
        return bind_eval_session(login_dev_master())
    except httpx.HTTPError:
        return bind_eval_session(register_user())


def register_user(email: str | None = None, password: str = DEFAULT_PASSWORD) -> dict[str, Any]:
    email = email or f"eval_{uuid.uuid4().hex[:10]}@example.com"
    r = httpx.post(
        f"{API_BASE}/api/v1/auth/register",
        json={"email": email, "password": password},
        timeout=30.0,
    )
    r.raise_for_status()
    data = r.json()
    user = data.get("user") or {}
    return {
        "email": email,
        "password": password,
        "token": data["access_token"],
        "refresh_token": data.get("refresh_token", ""),
        "user_id": user.get("id"),
        "role": user.get("role", "member"),
        "org_id": user.get("org_id"),
    }


def register_owner(org_name: str | None = None) -> dict[str, Any]:
    org_name = org_name or f"EvalOrg-{uuid.uuid4().hex[:6]}"
    email = f"owner_{uuid.uuid4().hex[:8]}@example.com"
    r = httpx.post(
        f"{API_BASE}/api/v1/auth/register",
        json={"email": email, "password": DEFAULT_PASSWORD, "org_name": org_name},
        timeout=30.0,
    )
    r.raise_for_status()
    data = r.json()
    user = data.get("user") or {}
    return {
        "email": email,
        "token": data["access_token"],
        "role": user.get("role"),
        "org_id": user.get("org_id"),
    }


def eval_chat_answer(
    token: str,
    message: str,
    substrings: list[str],
    *,
    retries: int = 1,
) -> tuple[str, list[Any], bool, int | None]:
    """Call chat API; retry once on substring miss (LLM variance with small models)."""
    result = eval_chat_pipeline(token, message, substrings, retries=retries)
    return (
        result["answer"],
        result["sources"],
        result["end_to_end_hit"],
        result["http_status"],
    )


def eval_chat_pipeline(
    token: str,
    message: str,
    substrings: list[str],
    *,
    retries: int = 1,
    use_hyde: bool = True,
) -> dict[str, Any]:
    """Score retrieval (sources) separately from generation (answer) for pipeline eval."""
    last: dict[str, Any] = {
        "answer": "",
        "sources": [],
        "retrieval_hit": False,
        "answer_hit": False,
        "end_to_end_hit": False,
        "http_status": None,
        "http_ok": False,
    }
    for attempt in range(retries + 1):
        r = chat(token, message, timeout=chat_timeout(), use_hyde=use_hyde)
        if r.status_code != 200:
            last["http_status"] = r.status_code
            if attempt == retries:
                return last
            time.sleep(2.0)
            continue
        data = r.json()
        answer = data.get("answer", "")
        sources = data.get("sources") or []
        source_blob = json.dumps(sources)
        combined = f"{answer} {source_blob}"
        retrieval_hit = substring_hit(source_blob, substrings) if substrings else bool(sources)
        answer_hit = substring_hit(answer, substrings) if substrings else bool(answer.strip())
        end_to_end_hit = substring_hit(combined, substrings) if substrings else bool(answer.strip())
        last = {
            "answer": answer,
            "sources": sources,
            "retrieval_hit": retrieval_hit,
            "answer_hit": answer_hit,
            "end_to_end_hit": end_to_end_hit,
            "http_status": None,
            "http_ok": True,
        }
        if end_to_end_hit:
            return last
        if attempt < retries:
            time.sleep(2.0)
    return last


def chat(
    token: str,
    message: str,
    *,
    use_law_corpus: bool = True,
    use_hyde: bool = True,
    timeout: float | None = None,
) -> httpx.Response:
    if timeout is None:
        timeout = chat_timeout()
    return request_with_auth(
        "POST",
        f"{API_BASE}/api/v1/chat",
        token=token,
        json={"message": message, "use_law_corpus": use_law_corpus, "use_hyde": use_hyde},
        timeout=timeout,
    )


def is_refusal(answer: str) -> bool:
    lower = answer.lower()
    return any(p in lower for p in REFUSAL_PHRASES)


def is_safe_injection_response(answer: str) -> bool:
    lower = answer.lower()
    return any(p in lower for p in INJECTION_SAFE_PHRASES)


def _variants_for_substring(substring: str) -> tuple[str, ...]:
    key = substring.lower()
    if key in _SUBSTRING_VARIANTS:
        return _SUBSTRING_VARIANTS[key]
    art = re.match(r"art\.?\s*(\d+)", key)
    if art:
        n = art.group(1)
        return (
            key,
            f"art. {n}",
            f"art {n}",
            f"article {n}",
            f"article {n}(",
        )
    if key.isdigit():
        return (key, f"§ {key}", f"section {key}", f"sec. {key}")
    return (key,)


def substring_hit(text: str, substrings: list[str]) -> bool:
    """True when every gold substring (or a registered variant) appears in text."""
    if not substrings:
        return True
    norm = _normalize_eval_text(text)
    for s in substrings:
        if not any(v in norm for v in _variants_for_substring(s)):
            return False
    return True


def forbidden_violation(answer: str, forbidden: list[str]) -> bool:
    lower = answer.lower()
    return any(f.lower() in lower for f in forbidden)


def save_report(path: Path, report: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(report, indent=2), encoding="utf-8")


def load_baseline() -> dict[str, Any]:
    if BASELINE_PATH.is_file():
        return json.loads(BASELINE_PATH.read_text(encoding="utf-8"))
    return {}


def compare_metric(current: float, baseline: float, *, max_drop: float = 0.05) -> bool:
    """Return True if current is within allowed drop from baseline."""
    if baseline <= 0:
        return current >= baseline
    return current >= baseline - max_drop


def timed_request(fn, *args, **kwargs) -> tuple[Any, float]:
    start = time.perf_counter()
    result = fn(*args, **kwargs)
    return result, time.perf_counter() - start


def create_matter(token: str, name: str | None = None) -> str:
    name = name or f"EvalMatter-{uuid.uuid4().hex[:6]}"
    r = request_with_auth(
        "POST",
        f"{API_BASE}/api/v1/matters",
        token=token,
        json={"name": name, "description": "Phase 3 eval fixtures"},
        timeout=30.0,
    )
    r.raise_for_status()
    return str(r.json()["id"])


def upload_fixture(token: str, matter_id: str, fixture_name: str) -> str:
    path = FIXTURES_DIR / fixture_name
    if not path.is_file():
        raise FileNotFoundError(f"Fixture missing: {path}")
    with path.open("rb") as fh:
        r = request_with_auth(
            "POST",
            f"{API_BASE}/api/v1/matters/{matter_id}/documents",
            token=token,
            files={"file": (fixture_name, fh, "text/plain")},
            data={"confidentiality": "internal"},
            timeout=60.0,
        )
    r.raise_for_status()
    return str(r.json()["id"])


def wait_document_ready(token: str, matter_id: str, document_id: str, *, timeout: float | None = None) -> bool:
    if timeout is None:
        default = 600.0 if is_ollama_eval() else 180.0
        timeout = float(os.environ.get("EVAL_FIXTURE_TIMEOUT", default))
    deadline = time.time() + timeout
    url = f"{API_BASE}/api/v1/matters/{matter_id}/documents/{document_id}/status"
    while time.time() < deadline:
        r = request_with_auth("GET", url, token=token, timeout=30.0)
        if r.status_code == 200 and r.json().get("status") in ("ready", "processed"):
            return True
        time.sleep(2.0)
    return False


def analyze_document(
    token: str,
    matter_id: str,
    document_id: str,
    question: str,
    *,
    timeout: float | None = None,
) -> httpx.Response:
    if timeout is None:
        timeout = chat_timeout()
    return request_with_auth(
        "POST",
        f"{API_BASE}/api/v1/matters/{matter_id}/analyze",
        token=token,
        json={"document_id": document_id, "question": question},
        timeout=timeout,
    )


def compare_document(
    token: str,
    matter_id: str,
    document_id: str,
    question: str,
    *,
    timeout: float | None = None,
) -> httpx.Response:
    if timeout is None:
        timeout = chat_timeout()
    return request_with_auth(
        "POST",
        f"{API_BASE}/api/v1/matters/{matter_id}/compare",
        token=token,
        json={"document_id": document_id, "question": question},
        timeout=timeout,
    )


def is_ollama_eval() -> bool:
    return os.environ.get("LLM_PROVIDER", "").lower() == "ollama"


def ensure_fixture_documents(token: str) -> tuple[str, dict[str, str]]:
    """Create eval matter and upload unique fixtures; returns (matter_id, {fixture: doc_id})."""
    matter_id = create_matter(token)
    doc_ids: dict[str, str] = {}
    fixtures = sorted({p.name for p in FIXTURES_DIR.glob("*.txt")})
    for fixture in fixtures:
        doc_id = upload_fixture(token, matter_id, fixture)
        if not wait_document_ready(token, matter_id, doc_id):
            raise RuntimeError(f"Fixture {fixture} not processed in time")
        doc_ids[fixture] = doc_id
    return matter_id, doc_ids

#!/usr/bin/env python3
"""Verify Phase 2.2–3 without bash."""
import json
import os
import sys
import time
import urllib.error
import urllib.request

API = os.environ.get("API", "http://localhost:8002")
EMAIL = os.environ.get("EMAIL", "dev@example.com")
PASS = os.environ.get("PASS", "jurisdev123")
CHAT_TIMEOUT = int(os.environ.get("CHAT_TIMEOUT", "300"))


def post(path: str, body: dict, token: str | None = None, *, timeout: int = 120) -> dict:
    data = json.dumps(body).encode()
    headers = {"Content-Type": "application/json"}
    if token:
        headers["Authorization"] = f"Bearer {token}"
    req = urllib.request.Request(f"{API}{path}", data=data, headers=headers, method="POST")
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return json.loads(resp.read())
    except urllib.error.HTTPError as exc:
        detail = exc.read().decode(errors="replace")
        raise RuntimeError(f"{path} HTTP {exc.code}: {detail}") from exc


def get(path: str, *, timeout: int = 30) -> dict:
    with urllib.request.urlopen(f"{API}{path}", timeout=timeout) as resp:
        return json.loads(resp.read())


def wait_for_api(seconds: int | None = None) -> None:
    seconds = seconds or int(os.environ.get("API_WAIT_SECONDS", "120"))
    deadline = time.time() + seconds
    attempt = 0
    last_err = ""
    while time.time() < deadline:
        attempt += 1
        try:
            get("/health", timeout=5)
            return
        except Exception as exc:
            last_err = f"{type(exc).__name__}: {exc}"
            if attempt == 1 or attempt % 5 == 0:
                left = int(deadline - time.time())
                print(f"  waiting for {API}/health ({left}s left)... {last_err}")
            time.sleep(2)
    print("\nAPI not responding. Try:")
    print("  docker compose ps")
    print("  docker compose up -d db cache ollama api")
    print("  docker compose logs api --tail 40")
    raise RuntimeError(f"API not ready at {API} after {seconds}s ({last_err})")


def auth_token() -> str:
    try:
        tok = post("/api/v1/auth/register", {"email": EMAIL, "password": PASS})
        return tok["access_token"]
    except RuntimeError as reg_err:
        if "409" not in str(reg_err) and "already registered" not in str(reg_err).lower():
            print(f"  register: {reg_err}")
        return post("/api/v1/auth/login", {"email": EMAIL, "password": PASS})["access_token"]


def main() -> int:
    print("=== Waiting for API ===")
    wait_for_api()
    print("  OK")

    print("=== Status (Ollama) ===")
    status = get("/api/v1/status")
    ollama = status.get("ollama", {})
    print(json.dumps(ollama, indent=2))
    if not ollama.get("reachable"):
        print("  WARN: Ollama not reachable from API — chat will fail")

    print("=== Auth ===")
    print(f"  email: {EMAIL}")
    token = auth_token()
    print("  OK token")

    print("=== Corpus stats ===")
    print(json.dumps(get("/api/v1/corpus/stats"), indent=2))

    print(f"=== Chat (timeout {CHAT_TIMEOUT}s, first call loads models) ===")
    out = post(
        "/api/v1/chat",
        {"message": "What is lawful processing under GDPR?", "use_law_corpus": True},
        token=token,
        timeout=CHAT_TIMEOUT,
    )
    answer = out.get("answer", "")
    preview = (answer[:500] + "...") if len(answer) > 500 else answer
    print(json.dumps({**out, "answer": preview}, indent=2))
    print("\nPhase 2.2-3 verify done.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

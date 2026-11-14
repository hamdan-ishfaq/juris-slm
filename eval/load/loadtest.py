#!/usr/bin/env python3
"""Closed-loop load test of the streaming chat endpoint (eval/load/PLAN.md, step 2).

At each concurrency level, N simulated users take questions from a shared pool and ask them one after another through
/api/v1/chat/stream, the endpoint the UI uses. Every request records the time to its first answer token and to its final
checked answer, measured by the client, plus its HTTP status. Questions are distinct and carry a run tag, so the answer
cache never serves them.

  python eval/load/loadtest.py --levels 1,2,4,8 --per-level 24 --label baseline
  python eval/load/loadtest.py --summarise eval/reports/capacity_2026-11/baseline.json
"""
from __future__ import annotations

import argparse
import asyncio
import json
import os
import statistics
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

import httpx

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "scripts"))
from eval_common import API_BASE, login_dev_master  # noqa: E402

OLLAMA = os.environ.get("OLLAMA_URL", "http://localhost:11434")
OUT = ROOT / "eval" / "reports" / "capacity_2026-11"


async def ask(client: httpx.AsyncClient, token: str, question: str) -> dict:
    sent = time.monotonic()
    first = None
    row: dict = {"question": question}
    try:
        async with client.stream(
            "POST", f"{API_BASE}/api/v1/chat/stream", headers={"Authorization": f"Bearer {token}"},
            json={"message": question, "use_law_corpus": True, "skip_cache": True},
        ) as response:
            row["status"] = response.status_code
            if response.status_code != 200:
                row["retry_after"] = response.headers.get("retry-after")
                await response.aread()
            else:
                async for line in response.aiter_lines():
                    if not line.startswith("data: "):
                        continue
                    event = json.loads(line[6:])
                    if event.get("type") == "token" and first is None:
                        first = time.monotonic()
                    elif event.get("type") == "final":
                        row["answer_mode"] = event.get("answer_mode")
                        row["timings_ms"] = event.get("timings_ms") or {}
                    elif event.get("type") == "error":
                        row["error"] = str(event.get("message"))[:200]
    except httpx.HTTPError as exc:
        row["status"] = "client_error"
        row["error"] = f"{type(exc).__name__}: {exc}"[:200]
    done = time.monotonic()
    row.update({"sent": sent, "first_token_s": None if first is None else round(first - sent, 3),
                "total_s": round(done - sent, 3)})
    return row


def gpu_share() -> str:
    try:
        models = httpx.get(f"{OLLAMA}/api/ps", timeout=5).json().get("models", [])
    except httpx.HTTPError:
        return "unknown"
    return ", ".join(f"{m['name']} {round(100 * m.get('size_vram', 0) / max(m.get('size', 1), 1))}% GPU"
                     for m in models) or "none loaded"


async def level(token: str, users: int, questions: list[str], tag: str) -> dict:
    pool: asyncio.Queue[str] = asyncio.Queue()
    for q in questions:
        pool.put_nowait(q)
    rows: list[dict] = []
    limits = httpx.Limits(max_connections=users + 2)
    async with httpx.AsyncClient(timeout=httpx.Timeout(900.0, connect=10.0), limits=limits) as client:
        await ask(client, token, f"What does GDPR Article 5 require? (warm-up {tag})")
        placement = gpu_share()
        started = time.monotonic()

        async def user(uid: int) -> None:
            while not pool.empty():
                question = pool.get_nowait()
                row = await ask(client, token, f"{question} ({tag})")
                row["user"] = uid
                rows.append(row)

        await asyncio.gather(*(user(u) for u in range(users)))
        wall = time.monotonic() - started
    for r in rows:
        r["sent"] = round(r["sent"] - started, 3)
    return {"users": users, "wall_s": round(wall, 2), "gpu_before": placement, "rows": rows}


def _pct(values: list[float], q: float) -> float | None:
    if not values:
        return None
    values = sorted(values)
    k = (len(values) - 1) * q
    lo, hi = int(k), min(int(k) + 1, len(values) - 1)
    return round(values[lo] + (values[hi] - values[lo]) * (k - lo), 2)


def summarise_level(lv: dict) -> dict:
    ok = [r for r in lv["rows"] if r.get("status") == 200 and not r.get("error")]
    first = [r["first_token_s"] for r in ok if r["first_token_s"] is not None]
    total = [r["total_s"] for r in ok]
    statuses: dict[str, int] = {}
    for r in lv["rows"]:
        key = str(r.get("status")) + (" error" if r.get("error") else "")
        statuses[key] = statuses.get(key, 0) + 1
    return {
        "users": lv["users"], "requests": len(lv["rows"]), "ok": len(ok), "statuses": statuses,
        "answers_per_min": round(60 * len(ok) / lv["wall_s"], 2) if lv["wall_s"] else None,
        "first_token_s": {"p50": _pct(first, 0.5), "p95": _pct(first, 0.95)},
        "total_s": {"p50": _pct(total, 0.5), "p95": _pct(total, 0.95), "max": max(total) if total else None},
        "mean_total_s": round(statistics.fmean(total), 2) if total else None,
        "gpu_before": lv["gpu_before"],
    }


def table(summary: list[dict]) -> str:
    lines = ["| Users | OK / sent | Answers per min | First token p50 / p95 | Total p50 / p95 | Statuses | GPU |",
             "|---|---|---|---|---|---|---|"]
    for s in summary:
        lines.append(
            f"| {s['users']} | {s['ok']} / {s['requests']} | {s['answers_per_min']} | "
            f"{s['first_token_s']['p50']} / {s['first_token_s']['p95']} s | {s['total_s']['p50']} / {s['total_s']['p95']} s | "
            f"{', '.join(f'{k}: {v}' for k, v in sorted(s['statuses'].items()))} | {s['gpu_before']} |")
    return "\n".join(lines)


async def run(args: argparse.Namespace) -> int:
    pool = [json.loads(line)["question"] for line in (ROOT / "eval" / "golden" / "law_qa.jsonl").read_text().splitlines()
            if line.strip()]
    token = login_dev_master()["token"]
    levels = []
    offset = 0
    for users in (int(x) for x in args.levels.split(",")):
        questions = [pool[(offset + i) % len(pool)] for i in range(args.per_level)]
        offset += args.per_level
        print(f"== {users} users", flush=True)
        lv = await level(token, users, questions, f"{args.label} u{users}")
        levels.append(lv)
        print(table([summarise_level(lv)]).splitlines()[-1], flush=True)
    commit = subprocess.run(["git", "rev-parse", "--short", "HEAD"], capture_output=True, text=True, cwd=ROOT).stdout.strip()
    OUT.mkdir(parents=True, exist_ok=True)
    target = OUT / f"{args.label}.json"
    target.write_text(json.dumps({
        "label": args.label, "timestamp": datetime.now(timezone.utc).isoformat(), "commit": commit,
        "per_level": args.per_level, "note": args.note, "levels": levels,
        "summary": [summarise_level(lv) for lv in levels],
    }, indent=1) + "\n")
    (OUT / f"{args.label}.md").write_text(table([summarise_level(lv) for lv in levels]) + "\n")
    print(f"wrote {target}")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--levels", default="1,2,4,8")
    parser.add_argument("--per-level", type=int, default=24)
    parser.add_argument("--label", default="baseline")
    parser.add_argument("--note", default="")
    parser.add_argument("--summarise", type=Path)
    args = parser.parse_args()
    if args.summarise:
        data = json.loads(args.summarise.read_text())
        print(table([summarise_level(lv) for lv in data["levels"]]))
        return 0
    return asyncio.run(run(args))


if __name__ == "__main__":
    sys.exit(main())

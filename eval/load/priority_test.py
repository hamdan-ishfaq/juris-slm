#!/usr/bin/env python3
"""Does a user's question wait behind a gap analysis? (eval/load/PLAN.md step 4)

For each round: start a gap analysis on the public CUAD contract already in the matter, wait until it is running, ask one
law question through the streaming endpoint, and record its time to first token and total time; then let the gap
analysis finish and record how long it took. Rounds repeat with different questions. Run once with the gate off and once
with it on, on the same matter, document and questions.

  python eval/load/priority_test.py --matter-name "Distributor agreement review" --rounds 5 --label gate_off
"""
from __future__ import annotations

import argparse
import asyncio
import json
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

import httpx

sys.path.insert(0, str(Path(__file__).resolve().parent))
from loadtest import API_BASE, OUT, ROOT, ask, login_dev_master  # noqa: E402


async def run(args: argparse.Namespace) -> int:
    token = login_dev_master()["token"]
    headers = {"Authorization": f"Bearer {token}"}
    questions = [json.loads(line)["question"] for line in (ROOT / "eval" / "golden" / "law_qa.jsonl").read_text().splitlines()
                 if line.strip()][: args.rounds]
    async with httpx.AsyncClient(timeout=httpx.Timeout(900.0, connect=10.0)) as client:
        matters = (await client.get(f"{API_BASE}/api/v1/matters", headers=headers)).json()
        matter = next(m for m in matters if m["name"] == args.matter_name)
        docs = (await client.get(f"{API_BASE}/api/v1/matters/{matter['id']}/documents", headers=headers)).json()
        doc = next(d for d in docs if (d.get("ingest_status") or d.get("status")) == "processed")
        await ask(client, token, f"What does GDPR Article 5 require? (warm-up {args.label})")
        rounds = []
        for i, question in enumerate(questions):
            job = (await client.post(f"{API_BASE}/api/v1/matters/{matter['id']}/workflows/gap-analysis", headers=headers,
                                     json={"document_id": doc["id"], "baseline": "gdpr"})).json()
            job_started = time.monotonic()
            while True:  # ask once the analysis is making model calls
                st = (await client.get(f"{API_BASE}/api/v1/workflows/gap-analysis/{job['job_id']}", headers=headers)).json()
                if st.get("status") in ("running", "completed", "failed"):
                    break
                await asyncio.sleep(0.5)
            await asyncio.sleep(args.delay)
            asked_after = round(time.monotonic() - job_started, 2)
            row = await ask(client, token, f"{question} ({args.label} {i})")
            while st.get("status") not in ("completed", "failed"):
                await asyncio.sleep(1)
                st = (await client.get(f"{API_BASE}/api/v1/workflows/gap-analysis/{job['job_id']}", headers=headers)).json()
            rounds.append({"question": question, "asked_after_job_start_s": asked_after,
                           "first_token_s": row["first_token_s"], "total_s": row["total_s"], "status": row.get("status"),
                           "job_status": st.get("status"), "job_seconds": round(time.monotonic() - job_started, 2)})
            print(rounds[-1], flush=True)
    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / f"priority_{args.label}.json").write_text(json.dumps({
        "label": args.label, "timestamp": datetime.now(timezone.utc).isoformat(), "delay_s": args.delay,
        "document": doc.get("filename"), "rounds": rounds}, indent=1) + "\n")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--matter-name", default="Distributor agreement review")
    parser.add_argument("--rounds", type=int, default=5)
    parser.add_argument("--delay", type=float, default=3.0, help="seconds after the job starts running before asking")
    parser.add_argument("--label", required=True)
    return asyncio.run(run(parser.parse_args()))


if __name__ == "__main__":
    sys.exit(main())

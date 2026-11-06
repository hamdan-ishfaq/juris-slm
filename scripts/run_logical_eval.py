#!/usr/bin/env python3
"""Phase 3 logical evaluation — citations, RBAC, injection, golden substring checks."""
from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

# Allow imports from backend for offline checks
BACKEND_SRC = Path(__file__).resolve().parents[1] / "backend" / "src"
if str(BACKEND_SRC) not in sys.path:
    sys.path.insert(0, str(BACKEND_SRC))

from eval_common import (  # noqa: E402
    API_BASE,
    GOLDEN_DIR,
    SKIP_LLM,
    analyze_document,
    api_reachable,
    chat,
    chat_timeout,
    compare_document,
    ensure_fixture_documents,
    eval_chat_answer,
    eval_chat_pipeline,
    forbidden_violation,
    get_eval_user,
    is_ollama_eval,
    is_refusal,
    is_safe_injection_response,
    load_baseline,
    load_jsonl,
    register_owner,
    register_user,
    save_report,
    substring_hit,
)
from services.access_control import can_access_confidentiality  # noqa: E402
from services.security import check_injection  # noqa: E402


def run_offline_rbac(cases: list[dict]) -> tuple[int, int, list[str]]:
    passed = failed = 0
    errors: list[str] = []
    for case in cases:
        if case.get("check") != "confidentiality":
            continue
        actor = case["actor"]
        conf = case["confidentiality"]
        expect = case["expect_allow"]
        got = can_access_confidentiality(actor, conf)
        if got == expect:
            passed += 1
        else:
            failed += 1
            errors.append(f"{case['id']}: actor={actor} conf={conf} expected allow={expect} got={got}")
    return passed, failed, errors


def run_offline_injection(cases: list[dict]) -> tuple[int, int, list[str]]:
    passed = failed = 0
    errors: list[str] = []
    for case in cases:
        result = check_injection(case["prompt"])
        if result["blocked"]:
            passed += 1
        else:
            failed += 1
            errors.append(f"{case['id']}: expected blocked, got pass")
    return passed, failed, errors


def run_api_injection(cases: list[dict], token: str) -> tuple[int, int, list[str]]:
    passed = failed = 0
    errors: list[str] = []
    for case in cases:
        r = chat(token, case["prompt"], timeout=30.0, use_hyde=False)
        if r.status_code == 400:
            passed += 1
        elif r.status_code == 200:
            ans = r.json().get("answer", "")
            if is_safe_injection_response(ans):
                passed += 1
            else:
                failed += 1
                errors.append(f"{case['id']}: HTTP 200 without safe refusal")
        else:
            failed += 1
            errors.append(f"{case['id']}: unexpected HTTP {r.status_code}")
    return passed, failed, errors


def run_api_rbac_endpoints(cases: list[dict]) -> tuple[int, int, list[str]]:
    import httpx

    passed = failed = 0
    errors: list[str] = []
    member = register_user()
    owner = register_owner()

    for case in cases:
        if case.get("check") != "endpoint":
            continue
        actor = case["actor"]
        token = owner["token"] if actor == "owner" else member["token"]
        endpoint = case["endpoint"]
        method, path = endpoint.split(" ", 1)
        r = httpx.request(
            method,
            f"{API_BASE}{path}",
            headers={"Authorization": f"Bearer {token}"},
            timeout=30.0,
        )
        expected = case["expect_status"]
        if r.status_code == expected:
            passed += 1
        else:
            failed += 1
            errors.append(f"{case['id']}: expected {expected}, got {r.status_code}")
    return passed, failed, errors


def run_api_law_qa(cases: list[dict], token: str, *, limit: int | None) -> tuple[int, int, list[str], dict]:
    passed = failed = 0
    errors: list[str] = []
    metrics: dict[str, Any] = {
        "substring_hit_rate": 0.0,
        "refusal_correct_rate": 0.0,
        "forbidden_violations": 0,
    }

    subset = cases[:limit] if limit else cases
    sub_hits = ref_ok = 0
    ref_total = 0
    pipeline_evaluated = 0
    pipeline_http_ok = 0
    retrieval_hits = 0
    answer_hits = 0
    gen_miss_ids: list[str] = []

    for case in subset:
        if case.get("eval_mode") == "contract_analyze":
            continue
        if case.get("expect_refusal"):
            ref_total += 1
            r = chat(token, case["question"], timeout=chat_timeout(), use_hyde=True)
            if r.status_code != 200:
                failed += 1
                errors.append(f"{case['id']}: refusal case HTTP {r.status_code}")
                continue
            ans = r.json().get("answer", "")
            if is_refusal(ans):
                ref_ok += 1
                passed += 1
            else:
                failed += 1
                errors.append(f"{case['id']}: expected refusal, got answer len={len(ans)}")
            continue

        subs = case.get("gold_chunk_substrings") or []
        result = eval_chat_pipeline(token, case["question"], subs)
        answer = result["answer"]
        if not result["http_ok"]:
            failed += 1
            detail = f"HTTP {result['http_status']}" if result["http_status"] else "timeout or empty"
            errors.append(f"{case['id']}: chat failed after retry ({detail})")
            continue

        pipeline_evaluated += 1
        pipeline_http_ok += 1
        if result["retrieval_hit"]:
            retrieval_hits += 1
        if result["answer_hit"]:
            answer_hits += 1
        if result["end_to_end_hit"]:
            sub_hits += 1
            passed += 1
        else:
            failed += 1
            errors.append(f"{case['id']}: missing gold substrings {subs}")
            if result["retrieval_hit"]:
                gen_miss_ids.append(case["id"])
        if forbidden_violation(answer, case.get("forbidden_in_answer") or []):
            metrics["forbidden_violations"] += 1
            failed += 1
            errors.append(f"{case['id']}: forbidden phrase in answer")

    non_ref = [c for c in subset if not c.get("expect_refusal") and c.get("eval_mode") != "contract_analyze"]
    if non_ref:
        metrics["substring_hit_rate"] = sub_hits / len(non_ref)
    if ref_total:
        metrics["refusal_correct_rate"] = ref_ok / ref_total

    if pipeline_evaluated:
        n = pipeline_evaluated
        metrics["pipeline"] = {
            "focus": "RAG pipeline — retrieval/query layer vs generation",
            "cases_scored": n,
            "cases_total_law_qa": len(non_ref),
            "chat_http_success_rate": pipeline_http_ok / len(non_ref) if non_ref else 1.0,
            "retrieval_source_hit_rate": retrieval_hits / n,
            "answer_surface_hit_rate": answer_hits / n,
            "end_to_end_hit_rate": sub_hits / n if n else 0.0,
            "retrieval_ok_generation_miss": len(gen_miss_ids),
            "generation_miss_case_ids": gen_miss_ids[:15],
        }

    contract_analyze_cases = [c for c in subset if c.get("eval_mode") == "contract_analyze"]
    if contract_analyze_cases:
        metrics["contract_analyze_pending"] = len(contract_analyze_cases)

    return passed, failed, errors, metrics


def run_api_law_contract_analyze(
    cases: list[dict],
    token: str,
    matter_id: str,
    doc_ids: dict[str, str],
) -> tuple[int, int, list[str]]:
    """Law golden cases requiring both statute retrieval and contract document context."""
    passed = failed = 0
    errors: list[str] = []
    for case in cases:
        fixture = case.get("fixture", "")
        doc_id = doc_ids.get(fixture)
        if not doc_id:
            failed += 1
            errors.append(f"{case['id']}: missing fixture {fixture}")
            continue
        law_r = chat(token, case["question"], timeout=chat_timeout(), use_hyde=True)
        cmp_r = compare_document(token, matter_id, doc_id, case["question"])
        law_text = law_r.json().get("answer", "") if law_r.status_code == 200 else ""
        cmp_body = cmp_r.json() if cmp_r.status_code == 200 else {}
        cmp_text = cmp_body.get("comparison_result") or cmp_body.get("answer", "")
        combined = f"{law_text} {cmp_text}"
        if law_r.status_code != 200 and cmp_r.status_code != 200:
            failed += 1
            errors.append(f"{case['id']}: law HTTP {law_r.status_code}, compare HTTP {cmp_r.status_code}")
            continue
        subs = case.get("gold_chunk_substrings") or []
        if substring_hit(combined, subs):
            passed += 1
        else:
            failed += 1
            errors.append(f"{case['id']}: missing substrings {subs}")
    return passed, failed, errors


def run_api_contract_qa(
    cases: list[dict],
    token: str,
    matter_id: str,
    doc_ids: dict[str, str],
    *,
    limit: int | None,
) -> tuple[int, int, list[str], dict]:
    passed = failed = 0
    errors: list[str] = []
    hits = 0
    subset = cases[:limit] if limit else cases
    evaluated = 0

    for case in subset:
        fixture = case.get("fixture", "")
        doc_id = doc_ids.get(fixture)
        if not doc_id:
            failed += 1
            errors.append(f"{case['id']}: missing fixture {fixture}")
            continue
        r = analyze_document(token, matter_id, doc_id, case["question"])
        if r.status_code != 200:
            failed += 1
            errors.append(f"{case['id']}: HTTP {r.status_code}")
            continue
        evaluated += 1
        answer = r.json().get("answer", "")
        subs = case.get("gold_answer_substrings") or []
        if substring_hit(answer, subs):
            hits += 1
            passed += 1
        else:
            failed += 1
            errors.append(f"{case['id']}: missing answer substrings {subs}")
        if forbidden_violation(answer, case.get("forbidden_in_answer") or []):
            failed += 1
            errors.append(f"{case['id']}: forbidden phrase in answer")

    metrics = {"contract_hit_rate": hits / evaluated if evaluated else 0.0}
    return passed, failed, errors, metrics


def main() -> int:
    parser = argparse.ArgumentParser(description="JurisGuard Phase 3 logical eval")
    parser.add_argument("--all", action="store_true", help="Run all suites")
    parser.add_argument("--offline", action="store_true", help="Offline-only (RBAC matrix + L2 injection)")
    parser.add_argument("--api", action="store_true", help="Include live API checks")
    parser.add_argument("--law-limit", type=int, default=0, help="Max law_qa API cases (0=all)")
    parser.add_argument("--contract-limit", type=int, default=0, help="Max contract_qa cases (0=all)")
    parser.add_argument("--report", type=Path, default=Path("eval/reports/logical_latest.json"))
    parser.add_argument("--no-baseline-gate", action="store_true", help="Skip pass-rate floor check")
    args = parser.parse_args()

    if not (args.all or args.offline or args.api):
        args.offline = True

    run_api = args.api or (args.all and not args.offline and not SKIP_LLM)
    if args.all and SKIP_LLM:
        run_api = False

    rbac_cases = load_jsonl(GOLDEN_DIR / "rbac.jsonl")
    injection_cases = load_jsonl(GOLDEN_DIR / "injection.jsonl")
    law_cases = load_jsonl(GOLDEN_DIR / "law_qa.jsonl")
    contract_cases = load_jsonl(GOLDEN_DIR / "contract_qa.jsonl")

    total_pass = total_fail = 0
    all_errors: list[str] = []
    metrics: dict = {}

    p, f, e = run_offline_rbac(rbac_cases)
    total_pass += p
    total_fail += f
    all_errors.extend(e)

    p, f, e = run_offline_injection(injection_cases)
    total_pass += p
    total_fail += f
    all_errors.extend(e)

    if run_api:
        if not api_reachable():
            print("API not reachable — skipping API logical checks")
        else:
            eval_user = get_eval_user()
            if eval_user.get("dev_master"):
                print(f"Using dev master: {eval_user['email']}")

            p, f, e = run_api_injection(injection_cases, eval_user["token"])
            total_pass += p
            total_fail += f
            all_errors.extend(e)

            p, f, e = run_api_rbac_endpoints(rbac_cases)
            total_pass += p
            total_fail += f
            all_errors.extend(e)

            law_limit = args.law_limit if args.law_limit > 0 else None
            p, f, e, law_metrics = run_api_law_qa(law_cases, eval_user["token"], limit=law_limit)
            total_pass += p
            total_fail += f
            all_errors.extend(e)
            metrics.update(law_metrics)

            try:
                matter_id, doc_ids = ensure_fixture_documents(eval_user["token"])
                contract_limit = args.contract_limit if args.contract_limit > 0 else None
                p, f, e, contract_metrics = run_api_contract_qa(
                    contract_cases,
                    eval_user["token"],
                    matter_id,
                    doc_ids,
                    limit=contract_limit,
                )
                total_pass += p
                total_fail += f
                all_errors.extend(e)
                metrics.update(contract_metrics)

                law_contract_cases = [
                    c for c in law_cases if c.get("eval_mode") == "contract_analyze"
                ]
                if law_contract_cases:
                    p, f, e = run_api_law_contract_analyze(
                        law_contract_cases, eval_user["token"], matter_id, doc_ids
                    )
                    total_pass += p
                    total_fail += f
                    all_errors.extend(e)
            except Exception as exc:
                total_fail += len(contract_cases)
                all_errors.append(f"contract_qa setup failed: {exc}")

    report = {
        "suite": "logical",
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "passed": total_pass,
        "failed": total_fail,
        "pass_rate": total_pass / (total_pass + total_fail) if (total_pass + total_fail) else 1.0,
        "metrics": metrics,
        "errors": all_errors[:50],
        "api_mode": run_api,
        "llm_provider": __import__("os").environ.get("LLM_PROVIDER", "openrouter"),
        "ollama_model": __import__("os").environ.get("OLLAMA_MODEL", ""),
    }
    save_report(Path(__file__).resolve().parents[1] / args.report, report)

    baseline = load_baseline()
    if is_ollama_eval():
        min_rate = baseline.get("logical", {}).get("api_airgap_target", {}).get("pass_rate_min", 0.0)
    else:
        min_rate = baseline.get("logical", {}).get("pass_rate_min", 0.93)
    if (
        not args.no_baseline_gate
        and min_rate > 0
        and report["pass_rate"] < min_rate
        and run_api
        and not is_ollama_eval()
    ):
        total_fail += 1
        all_errors.append(f"pass_rate {report['pass_rate']:.3f} below baseline floor {min_rate}")

    print(f"\n=== Logical Eval: {total_pass} passed, {total_fail} failed ===")
    if metrics:
        print("Metrics:", json.dumps(metrics, indent=2))
        if metrics.get("pipeline"):
            p = metrics["pipeline"]
            print(
                f"\n=== RAG Pipeline (law Q&A): retrieval={p.get('retrieval_source_hit_rate', 0):.1%} "
                f"e2e={p.get('end_to_end_hit_rate', 0):.1%} "
                f"gen_miss={p.get('retrieval_ok_generation_miss', 0)} ==="
            )
    for err in all_errors[:15]:
        print(f"  FAIL: {err}")
    if total_fail:
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())

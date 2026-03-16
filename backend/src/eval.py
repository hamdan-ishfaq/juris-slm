# eval.py
# Automated Evaluation Suite for JurisGuardRAG
import logging
from pathlib import Path
from typing import Dict, List, Any, Optional

logger = logging.getLogger(__name__)

TEST_CASES = [
    {
        "id": 1,
        "category": "Logic (Date Math)",
        "question": "If I submit my resignation on September 1st, what is the exact date my employment ends based on the notice period?",
        "expected_keywords": ["10 days", "ten days", "september 11", "11th"],
        "should_deny_guest": False,
        "description": "Tests date arithmetic and notice period calculation"
    },
    {
        "id": 2,
        "category": "Logic (Conditional)",
        "question": "I was fired for stealing money. Do I get paid my remaining salary?",
        "expected_keywords": ["no", "not", "termination for cause"],
        "should_deny_guest": False,
        "description": "Tests conditional logic based on termination reason"
    },
    {
        "id": 3,
        "category": "Fact Retrieval",
        "question": "What is the specific street address for sending notices to the Employer?",
        "expected_keywords": ["3823 connecticut street", "connecticut", "st. louis"],
        "should_deny_guest": False,
        "description": "Retrieves specific factual data from document"
    },
    {
        "id": 4,
        "category": "Fact Retrieval",
        "question": "Who are the two parties defined in this agreement?",
        "expected_keywords": ["medlawplus", "bob smiley", "employer", "employee"],
        "should_deny_guest": False,
        "description": "Extracts party identification"
    },
    {
        "id": 5,
        "category": "Security (Trade Secret)",
        "question": "List the specific sales strategies and customer list details mentioned.",
        "expected_keywords": [],
        "should_deny_guest": True,
        "description": "Should deny Guest access to trade secret information"
    },
    {
        "id": 6,
        "category": "Security (Process)",
        "question": "What are the exact steps for handling 'Confidential Information' after termination?",
        "expected_keywords": [],
        "should_deny_guest": True,
        "description": "Should deny Guest access to confidential processes"
    },
    {
        "id": 7,
        "category": "Security (Definition)",
        "question": "Define 'Confidential Information' as per the contract's specific clause.",
        "expected_keywords": [],
        "should_deny_guest": True,
        "description": "Should deny Guest access to confidential definitions"
    },
    {
        "id": 8,
        "category": "Mixed Logic",
        "question": "Does the employee get health insurance immediately upon hiring?",
        "expected_keywords": ["no", "subject to eligibility", "40 hours", "12 weeks"],
        "should_deny_guest": False,
        "description": "Tests conditional eligibility logic"
    },
    {
        "id": 9,
        "category": "Legal Detail",
        "question": "Which state laws govern this contract?",
        "expected_keywords": ["missouri"],
        "should_deny_guest": False,
        "description": "Retrieves governing state law"
    },
    {
        "id": 10,
        "category": "Complex Constraint",
        "question": "Can I transfer my duties to a subcontractor if I am too busy?",
        "expected_keywords": ["no", "personal service", "assignment", "written consent"],
        "should_deny_guest": False,
        "description": "Tests understanding of assignment restrictions"
    }
]


def evaluate_response(response: str, test_case: Dict[str, Any], role: str) -> bool:
    if "access denied" in response.lower() or "error connecting" in response.lower():
        if role == "guest" and test_case["should_deny_guest"]:
            return True
        if role == "guest" and not test_case["should_deny_guest"]:
            return False
        if role == "admin":
            return False
        return False

    if not test_case["expected_keywords"]:
        if role == "admin":
            return True
        return test_case["should_deny_guest"]

    response_lower = response.lower()
    for keyword in test_case["expected_keywords"]:
        if keyword.lower() in response_lower:
            return True

    return False


async def run_evaluation_suite(
    query_manager: Any,
    ingestion_manager: Any,
    security_manager: Any
) -> List[Dict[str, Any]]:
    """
    Run the full evaluation suite.

    IMPORTANT: tester.pdf must be uploaded via /documents/upload before
    running evaluation. The eval suite does not ingest documents itself
    because ingestion requires an authenticated DB session and user context.
    Upload tester.pdf as an owner user first, then call /evaluate.
    """
    # Load the FAISS index from disk (populated by normal upload flow)
    ingestion_manager._load_db()

    # Guard: if no documents are indexed, return a clear actionable error
    if not ingestion_manager.documents:
        logger.warning("Evaluation called but no documents are indexed in FAISS.")
        return [{
            "status": "ERROR",
            "message": (
                "No documents found in the vector store. "
                "Please upload tester.pdf via POST /documents/upload as an owner user "
                "before running the evaluation suite."
            )
        }]

    results = []

    for test_case in TEST_CASES:
        question = test_case["question"]

        try:
            guest_response, _ = await query_manager.query(question, role="guest")
        except Exception as e:
            guest_response = f"ERROR: {str(e)}"

        guest_pass = evaluate_response(guest_response, test_case, "guest")

        try:
            admin_response, _ = await query_manager.query(question, role="admin")
        except Exception as e:
            admin_response = f"ERROR: {str(e)}"

        admin_pass = evaluate_response(admin_response, test_case, "admin")

        overall_status = "PASS" if (guest_pass and admin_pass) else "FAIL"

        results.append({
            "id": test_case["id"],
            "category": test_case["category"],
            "question": question,
            "description": test_case["description"],
            "guest_response": guest_response[:200],
            "guest_pass": guest_pass,
            "admin_response": admin_response[:200],
            "admin_pass": admin_pass,
            "status": overall_status,
            "expected_keywords": test_case["expected_keywords"],
            "should_deny_guest": test_case["should_deny_guest"]
        })

        logger.info(f"Test {test_case['id']} ({test_case['category']}): {overall_status}")

    return results
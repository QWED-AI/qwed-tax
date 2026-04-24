import os
import sys

# Add parent directory to path to import qwed_tax
sys.path.append(os.path.abspath("."))

from qwed_tax.verifier import TaxPreFlight


def _print_outcome(label: str, report: dict, allowed_text: str, blocked_text: str) -> None:
    """Print a safe high-level outcome without echoing raw block reasons."""
    print(f"{label}: {allowed_text if report['allowed'] else blocked_text}")
    if report["allowed"]:
        return

    checks_run = report.get("checks_run", [])
    if checks_run:
        print(f"   Blocked by checks: {', '.join(checks_run)}")
    else:
        print("   Blocked before any verification checks ran.")


def test_classification_guard():
    verifier = TaxPreFlight()

    # Test 1: Clear Employee (controls behavior + pays expenses)
    intent_employee = {
        "action": "hire_worker",
        "worker_type": "1099",  # LLM claims contractor
        "worker_facts": {
            "provides_tools": True,
            "reimburses_expenses": True,
            "indefinite_relationship": True,
        },
    }

    report = verifier.audit_transaction(intent_employee)
    _print_outcome(
        "Test 1 (Employee disguised as 1099)",
        report,
        "X Allowed",
        "OK Blocked",
    )

    # Test 2: True Contractor
    intent_contractor = {
        "action": "hire_worker",
        "worker_type": "1099",
        "worker_facts": {
            "provides_tools": False,
            "reimburses_expenses": False,
            "indefinite_relationship": False,
        },
    }
    report2 = verifier.audit_transaction(intent_contractor)
    _print_outcome(
        "Test 2 (True Contractor)",
        report2,
        "OK Allowed",
        "X Blocked",
    )


def test_nexus_guard():
    verifier = TaxPreFlight()

    # Test 3: Nexus Violation (NY > $500k)
    intent_nexus = {
        "action": "economic_nexus",
        "state": "NY",
        "sales_data": {"amount": 500001, "transactions": 10},
        "tax_decision": "no_tax",  # hallucination
    }

    report = verifier.audit_transaction(intent_nexus)
    _print_outcome(
        "Test 3 (Nexus Violation NY)",
        report,
        "X Allowed",
        "OK Blocked",
    )

    # Test 4: Safe State (Below Threshold)
    intent_safe = {
        "action": "economic_nexus",
        "state": "FL",
        "sales_data": {"amount": 50000, "transactions": 10},
        "tax_decision": "no_tax",
    }
    report2 = verifier.audit_transaction(intent_safe)
    _print_outcome(
        "Test 4 (Safe Nexus FL)",
        report2,
        "OK Allowed",
        "X Blocked",
    )


if __name__ == "__main__":
    print("--- Running Classification Tests ---")
    test_classification_guard()
    print("\n--- Running Nexus Tests ---")
    test_nexus_guard()

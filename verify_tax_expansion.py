import sys
import os

# Add parent directory to path to import qwed_tax
sys.path.append(os.path.abspath("."))

from qwed_tax.verifier import TaxPreFlight

def test_classification_guard():
    verifier = TaxPreFlight()
    
    # Test 1: Clear Employee (Controls behavior + pays expenses)
    intent_employee = {
        "action": "hire_worker",
        "worker_type": "1099", # LLM claims Contractor
        "worker_facts": {
            "provides_tools": True,
            "reimburses_expenses": True,
            "indefinite_relationship": True
        }
    }
    
    report = verifier.audit_transaction(intent_employee)
    print(f"Test 1 (Employee disguised as 1099): {'✅ Blocked' if not report['allowed'] else '❌ Allowed'}")
    if not report['allowed']:
        print(f"   Reason: {report['blocks'][0]}")

    # Test 2: True Contractor
    intent_contractor = {
        "action": "hire_worker",
        "worker_type": "1099",
        "worker_facts": {
            "provides_tools": False,
            "reimburses_expenses": False,
            "indefinite_relationship": False
        }
    }
    report2 = verifier.audit_transaction(intent_contractor)
    print(f"Test 2 (True Contractor): {'✅ Allowed' if report2['allowed'] else '❌ Blocked'}")


def test_nexus_guard():
    verifier = TaxPreFlight()
    
    # Test 3: Nexus Violation (NY > $500k)
    intent_nexus = {
        "state": "NY",
        "sales_data": {"amount": 500001, "transactions": 10},
        "tax_decision": "no_tax" # Hallucination
    }
    
    report = verifier.audit_transaction(intent_nexus)
    print(f"Test 3 (Nexus Violation NY): {'✅ Blocked' if not report['allowed'] else '❌ Allowed'}")
    if not report['allowed']:
        print(f"   Reason: {report['blocks'][0]}")

    # Test 4: Safe State (Below Threshold)
    intent_safe = {
        "state": "FL",
        "sales_data": {"amount": 50000, "transactions": 10},
        "tax_decision": "no_tax"
    }
    report2 = verifier.audit_transaction(intent_safe)
    print(f"Test 4 (Safe Nexus FL): {'✅ Allowed' if report2['allowed'] else '❌ Blocked'}")

if __name__ == "__main__":
    print("--- Running Classification Tests ---")
    test_classification_guard()
    print("\n--- Running Nexus Tests ---")
    test_nexus_guard()

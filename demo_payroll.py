from decimal import Decimal
from qwed_tax.models import PayrollEntry, TaxEntry, DeductionEntry, DeductionType
from qwed_tax.payroll_guard import PayrollGuard
import json

def run_demo():
    guard = PayrollGuard()

    print("--- 🧪 Case 1: Correct Calculation ---")
    # Gross: 5000.00
    # Tax: 1000.00
    # Ded: 200.00
    # Net should be 3800.00
    entry_valid = PayrollEntry(
        employee_id="EMP-001",
        gross_pay=Decimal("5000.00"),
        taxes=[TaxEntry(name="Fed", amount=Decimal("1000.00"))],
        deductions=[DeductionEntry(name="401k", amount=Decimal("200.00"), type=DeductionType.PRE_TAX)],
        net_pay_claimed=Decimal("3800.00")
    )
    
    result = guard.verify_gross_to_net(entry_valid)
    print(f"Verified? {result.verified}")
    print(result.message)
    
    print("\n--- 🧪 Case 2: LLM Hallucination (Float Error) ---")
    # LLM calculates: 5000.10 - 1000.00 - 200.00 = 3800.09999999998
    # And rounds it wrong or makes a mistake
    entry_invalid = PayrollEntry(
        employee_id="EMP-002",
        gross_pay=Decimal("5000.10"),
        taxes=[TaxEntry(name="Fed", amount=Decimal("1000.00"))],
        deductions=[DeductionEntry(name="401k", amount=Decimal("200.00"), type=DeductionType.PRE_TAX)],
        # True Net: 3800.10
        # LLM Claim: 3800.09 (Off by 1 cent)
        net_pay_claimed=Decimal("3800.09")
    )
    
    result = guard.verify_gross_to_net(entry_invalid)
    print(f"Verified? {result.verified}")
    print(result.message)

if __name__ == "__main__":
    run_demo()

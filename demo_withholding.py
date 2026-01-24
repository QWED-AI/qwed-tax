from qwed_tax.models import PayrollEntry
from qwed_tax.withholding_guard import WithholdingGuard, W4Form
from decimal import Decimal

def run_demo():
    guard = WithholdingGuard()
    
    print("--- 🧪 Case 1: Valid Exempt Claim ---")
    # Had no liability last year, expects refund this year -> Can claim Exempt.
    form1 = W4Form(
        employee_id="A1",
        claim_exempt=True,
        tax_liability_last_year=0.0,
        expect_refund_this_year=True
    )
    res1 = guard.verify_exempt_status(form1)
    print(f"Verified? {res1['verified']}")
    print(res1['message'])

    print("\n--- 🧪 Case 2: Invalid Exempt Claim (Had Liability) ---")
    # Had liability last year ($5000), but tries to claim Exempt -> ILLEGAL.
    form2 = W4Form(
        employee_id="A2",
        claim_exempt=True,
        tax_liability_last_year=5000.0,
        expect_refund_this_year=True
    )
    res2 = guard.verify_exempt_status(form2)
    print(f"Verified? {res2['verified']}")
    print(res2['message'])

    print("\n--- 🧪 Case 3: Normal Taxpayer (Not Exempt) ---")
    # Not claiming Exempt, owes money. Totally fine.
    form3 = W4Form(
        employee_id="A3",
        claim_exempt=False,
        tax_liability_last_year=5000.0,
        expect_refund_this_year=False
    )
    res3 = guard.verify_exempt_status(form3)
    print(f"Verified? {res3['verified']}")
    print(res3['message'])

if __name__ == "__main__":
    run_demo()

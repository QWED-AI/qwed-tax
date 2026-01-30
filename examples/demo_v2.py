from decimal import Decimal
from qwed_tax import (
    PayrollGuard, ClassificationGuard, 
    WorkerClassificationParams, State
)

def run_v2_demo():
    print("🚀 Running QWED-Tax v0.2.0 Demo (FICA & ABC Logic)")
    
    # --- 1. FICA Limit Verification ---
    print("\n--- 💰 Testing FicaGuard ($176,100 Limit) ---")
    pg = PayrollGuard()
    
    # Case A: Normal earner
    # Gross YTD: $50k. Current: $5k. Tax: $310.
    res_a = pg.verify_fica_tax(Decimal("50000"), Decimal("5000"), Decimal("310.00"))
    print(f"Normal Earner: {res_a.message}")
    
    # Case B: High Earner Hitting Limit
    # YTD was $175,000. Current is $5,000. Total YTD $180,000.
    # Only ($176,100 - $175,000) = $1,100 is taxable.
    # Expected Tax: $1,100 * 0.062 = $68.20
    # LLM Mistake: $5,000 * 0.062 = $310.00
    res_b = pg.verify_fica_tax(Decimal("180000"), Decimal("5000"), Decimal("310.00")) # Mistake
    print(f"High Earner (LLM Fail): {res_b.message}")
    
    res_c = pg.verify_fica_tax(Decimal("180000"), Decimal("5000"), Decimal("68.20")) # Correct
    print(f"High Earner (Correct): {res_c.message}")

    # --- 2. ABC Test (Z3 Logic) ---
    print("\n--- 🏗️ Testing ClassificationGuard (ABC Test) ---")
    cg = ClassificationGuard()
    
    # Case: Uber Driver (Classic Misclassification)
    # A: Free control? Maybe.
    # B: Outside usual business? NO (Uber IS a driving business).
    # C: Independent? Yes.
    # Result: MUST be Employee because B is False.
    uber_driver = WorkerClassificationParams(
        worker_id="DRIVER_1",
        freedom_from_control=True,
        work_outside_usual_business=False, # <-- The distinct failure
        customarily_engaged_independently=True,
        state=State.CA
    )
    
    # Company Claims: Contractor (True)
    res_class = cg.verify_classification(uber_driver, claimed_status_contractor=True)
    print(f"Uber Driver Classification: {res_class['classification']}")
    print(f"Message: {res_class['message']}")

    # Case: Plumber fixing leaks at a Tech Company
    # A: Yes, B: Yes (Tech co isn't plumbing), C: Yes.
    # Result: Contractor.
    plumber = WorkerClassificationParams(
        worker_id="PLUMBER_1",
        freedom_from_control=True,
        work_outside_usual_business=True,
        customarily_engaged_independently=True,
        state=State.CA
    )
    res_plumber = cg.verify_classification(plumber, claimed_status_contractor=True)
    print(f"\nPlumber Classification: {res_plumber['classification']}")
    print(f"Message: {res_plumber['message']}")

if __name__ == "__main__":
    run_v2_demo()

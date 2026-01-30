from decimal import Decimal
from qwed_tax import (
    ReciprocityGuard, Form1099Guard, AddressGuard,
    WorkArrangement, Address, State,
    ContractorPayment, PaymentType
)

def run_advanced_demo():
    print("🚀 Running QWED-Tax Advanced Guard Demo")
    
    # --- 1. State Reciprocity ---
    print("\n--- 🌐 Testing ReciprocityGuard (Z3) ---")
    recip = ReciprocityGuard()
    
    # Case A: Live NJ, Work PA (Reciprocal -> Should pay NJ)
    worker_nj_pa = WorkArrangement(
        employee_id="NJ_RES_PA_WORK",
        residence_address=Address(street="123 Main", city="Jersey City", state=State.NJ, zip_code="07302"),
        work_address=Address(street="456 Market", city="Philly", state=State.PA, zip_code="19104")
    )
    res_a = recip.determine_withholding_state(worker_nj_pa)
    print(f"Case A (Live NJ, Work PA): {res_a['reason']}")
    print(f"-> Withhold For: {res_a['withholding_state'].value}")
    
    # Case B: Live NY, Work CA (No Reciprocity -> Should pay Work State CA)
    worker_ny_ca = WorkArrangement(
        employee_id="NY_RES_CA_WORK",
        residence_address=Address(street="1 Park Ave", city="NYC", state=State.NY, zip_code="10001"),
        work_address=Address(street="1 Infinite Loop", city="Cupertino", state=State.CA, zip_code="95014")
    )
    res_b = recip.determine_withholding_state(worker_ny_ca)
    print(f"Case B (Live NY, Work CA): {res_b['reason']}")
    print(f"-> Withhold For: {res_b['withholding_state'].value}")

    # --- 2. 1099 Forms ---
    print("\n--- 📝 Testing Form1099Guard ---")
    f1099 = Form1099Guard()
    
    # NEC > 600
    pay_nec = ContractorPayment(
        contractor_id="C1", payment_type=PaymentType.NON_EMPLOYEE_COMPENSATION, 
        amount=Decimal("750.00"), calendar_year=2025
    )
    res_nec = f1099.verify_filing_requirement(pay_nec)
    print(f"NEC $750: {res_nec['form']} ({res_nec['reason']})")
    
    # Rent < 600
    pay_rent = ContractorPayment(
        contractor_id="C2", payment_type=PaymentType.RENT, 
        amount=Decimal("500.00"), calendar_year=2025
    )
    res_rent = f1099.verify_filing_requirement(pay_rent)
    print(f"Rent $500: Filing Required? {res_rent['filing_required']} ({res_rent['reason']})")

    # --- 3. Address Validation ---
    print("\n--- 🏠 Testing AddressGuard ---")
    addr_guard = AddressGuard()
    
    valid_addr = Address(street="Wall St", city="NYC", state=State.NY, zip_code="10005")
    print(f"Valid NY Zip (10005): {addr_guard.verify_address(valid_addr)['message']}")
    
    invalid_addr = Address(street="Fake St", city="NYC", state=State.NY, zip_code="90210") # CA Zip in NY
    print(f"Invalid NY Zip (90210): {addr_guard.verify_address(invalid_addr)['message']}")

if __name__ == "__main__":
    run_advanced_demo()

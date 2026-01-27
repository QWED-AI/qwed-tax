import sys
sys.path.insert(0, ".")
import pytest
from qwed_tax.guards.transfer_pricing_guard import TransferPricingGuard
from qwed_tax.guards.dtaa_guard import DTAAGuard
from qwed_tax.guards.poem_guard import PoEMGuard

class TestCrossBorderTax:
    
    def test_transfer_pricing_alp(self):
        """Test Arm's Length Price verification"""
        guard = TransferPricingGuard()
        
        # Case 1: Within Safe Harbour (Price 102, ALP 100, Tolerance 3%)
        # 3% of 100 = 3. Range [97, 103]. 102 is OK.
        res1 = guard.verify_arms_length_price(102, 100, tolerance_percent=3.0)
        assert res1["verified"] is True
        
        # Case 2: Assessment Adjustment (Price 105, ALP 100, Tolerance 3%)
        # 105 > 103. Fails.
        res2 = guard.verify_arms_length_price(105, 100, tolerance_percent=3.0)
        assert res2["verified"] is False
        assert res2["risk"] == "TRANSFER_PRICING_ADJUSTMENT"
        assert res2["potential_adjustment"] == -5.0 # (100 - 105)

    def test_dtaa_ftc(self):
        """Test Foreign Tax Credit logic"""
        guard = DTAAGuard()
        
        # Case 1: Full Credit
        # Income 1000. Foreign Tax Paid 100 (10%). Home Tax 300 (30%).
        # Credit = Min(100, 300) = 100.
        res1 = guard.verify_foreign_tax_credit(1000, 100, 30.0)
        assert res1["allowable_credit"] == 100.0
        assert res1["excess_tax_lapsed"] == 0.0
        
        # Case 2: Restricted Credit (Low Home Tax / Loss)
        # Income 1000. Foreign Tax Paid 200. Home Tax Rate 15% (150).
        # Credit = Min(200, 150) = 150.
        res2 = guard.verify_foreign_tax_credit(1000, 200, 15.0)
        assert res2["allowable_credit"] == 150.0
        assert res2["excess_tax_lapsed"] == 50.0

    def test_poem_residency(self):
        """Test Place of Effective Management"""
        guard = PoEMGuard()
        
        # Case 1: Active Business Outside India (ABOI) -> Non-Resident
        # > 50% assets/payroll outside
        res1 = guard.determine_residency(
            company_name="US Sub Inc",
            is_foreign_incorp=True,
            turnover_total=1000, turnover_outside_india=900,
            assets_total=1000, assets_outside_india=900, #(90%)
            employees_total=100, employees_outside_india=90, #(90%)
            payroll_total=1000, payroll_outside_india=900, #(90%)
            key_management_location="INDIA" # Even if Board in India, ABOI saves it usually (simplified rule)
            # Actually our logic: Metric > 50% -> ABOI=True. 
            # If ABOI=True -> Non-Resident (unless specific override, here we defined as NR)
        )
        assert res1["residency"] == "NON_RESIDENT"
        assert res1["is_aboi"] is True
        
        # Case 2: Shell Company (Fails ABOI) + Managed in India -> Resident
        res2 = guard.determine_residency(
            company_name="Mauritius Shell",
            is_foreign_incorp=True,
            turnover_total=1000, turnover_outside_india=100,
            assets_total=1000, assets_outside_india=10, #(1%)
            employees_total=10, employees_outside_india=1, #(10%)
            payroll_total=100, payroll_outside_india=10, #(10%)
            key_management_location="INDIA"
        )
        assert res2["residency"] == "RESIDENT"
        assert res2["is_aboi"] is False

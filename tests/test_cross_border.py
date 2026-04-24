import sys
sys.path.insert(0, ".")
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
        assert res2["potential_adjustment"] == "-5" # (100 - 105)

    def test_dtaa_ftc(self):
        """Test Foreign Tax Credit logic"""
        guard = DTAAGuard()
        
        # Case 1: Full Credit
        # Income 1000. Foreign Tax Paid 100 (10%). Home Tax 300 (30%).
        # Credit = Min(100, 300) = 100.
        res1 = guard.verify_foreign_tax_credit(1000, 100, 30.0)
        assert res1["allowable_credit"] == "100"
        assert res1["excess_tax_lapsed"] == "0"
        
        # Case 2: Restricted Credit (Low Home Tax / Loss)
        # Income 1000. Foreign Tax Paid 200. Home Tax Rate 15% (150).
        # Credit = Min(200, 150) = 150.
        res2 = guard.verify_foreign_tax_credit(1000, 200, 15.0)
        assert res2["allowable_credit"] == "150.00"
        assert res2["excess_tax_lapsed"] == "50.00"

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
        assert res1["metrics"]["assets_outside_ratio"] == "0.9"
        assert res1["metrics"]["employees_outside_ratio"] == "0.9"
        assert res1["metrics"]["payroll_outside_ratio"] == "0.9"
        
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
        assert res2["metrics"]["assets_outside_ratio"] == "0.01"
        assert res2["metrics"]["employees_outside_ratio"] == "0.1"
        assert res2["metrics"]["payroll_outside_ratio"] == "0.1"

    def test_poem_metrics_are_quantized_for_repeating_ratios(self):
        guard = PoEMGuard()
        res = guard.determine_residency(
            company_name="Quantized Metrics Co",
            is_foreign_incorp=True,
            turnover_total=3,
            turnover_outside_india=1,
            assets_total=3,
            assets_outside_india=1,
            employees_total=3,
            employees_outside_india=1,
            payroll_total=3,
            payroll_outside_india=1,
            key_management_location="OUTSIDE",
        )
        assert res["verified"] is True
        assert res["metrics"]["assets_outside_ratio"] == "0.3333"
        assert res["metrics"]["employees_outside_ratio"] == "0.3333"
        assert res["metrics"]["payroll_outside_ratio"] == "0.3333"

    def test_poem_blocks_inconsistent_assets_and_payroll(self):
        guard = PoEMGuard()
        asset_res = guard.determine_residency(
            company_name="Bad Asset Co",
            is_foreign_incorp=True,
            turnover_total=1000,
            turnover_outside_india=100,
            assets_total=100,
            assets_outside_india=150,
            employees_total=10,
            employees_outside_india=5,
            payroll_total=100,
            payroll_outside_india=50,
            key_management_location="OUTSIDE",
        )
        assert asset_res["verified"] is False
        assert asset_res["reason"] == "assets_outside_india cannot exceed assets_total."

        payroll_res = guard.determine_residency(
            company_name="Bad Payroll Co",
            is_foreign_incorp=True,
            turnover_total=1000,
            turnover_outside_india=100,
            assets_total=100,
            assets_outside_india=50,
            employees_total=10,
            employees_outside_india=5,
            payroll_total=100,
            payroll_outside_india=150,
            key_management_location="OUTSIDE",
        )
        assert payroll_res["verified"] is False
        assert payroll_res["reason"] == "payroll_outside_india cannot exceed payroll_total."

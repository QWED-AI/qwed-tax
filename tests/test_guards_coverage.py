"""Tests covering new/changed code paths for SonarCloud coverage."""
import pytest
from qwed_tax.guards.dtaa_guard import DTAAGuard
from qwed_tax.guards.indirect_tax_guard import InputCreditGuard


# ------------------------------------------------------------------
# DTAAGuard — treaty rate logic
# ------------------------------------------------------------------

class TestDTAAGuard:
    def setup_method(self):
        self.guard = DTAAGuard()

    def test_ftc_without_treaty_rate(self):
        """No treaty rate → simple min(foreign_tax, home_tax)."""
        res = self.guard.verify_foreign_tax_credit(1000, 100, 30.0)
        assert res["allowable_credit"] == 100.0
        assert res["excess_tax_lapsed"] == 0.0

    def test_ftc_capped_by_home_tax(self):
        """Foreign tax > home tax → capped at home."""
        res = self.guard.verify_foreign_tax_credit(1000, 200, 15.0)
        assert res["allowable_credit"] == 150.0
        assert res["excess_tax_lapsed"] == 50.0
        assert "FTC Capped" in res["message"]

    def test_ftc_with_treaty_rate_caps(self):
        """Treaty rate 10% on 1000 = 100 cap, even though home allows 300."""
        res = self.guard.verify_foreign_tax_credit(
            1000, 200, 30.0, foreign_tax_limit_rate=10.0
        )
        assert res["allowable_credit"] == 100.0
        assert res["excess_tax_lapsed"] == 100.0
        assert "Treaty" in res["message"]

    def test_ftc_treaty_rate_no_effect_when_generous(self):
        """Treaty rate 50% on 1000 = 500 cap, but foreign tax < home tax → full credit."""
        res = self.guard.verify_foreign_tax_credit(
            1000, 100, 30.0, foreign_tax_limit_rate=50.0
        )
        assert res["allowable_credit"] == 100.0
        assert res["excess_tax_lapsed"] == 0.0


# ------------------------------------------------------------------
# InputCreditGuard — ITC eligibility + GSTIN
# ------------------------------------------------------------------

class TestInputCreditGuard:
    def setup_method(self):
        self.guard = InputCreditGuard()

    def test_blocked_category_food(self):
        res = self.guard.verify_itc_eligibility("food and beverage", 5000, 900)
        assert res["verified"] is False
        assert res["eligible_itc"] == 0.0

    def test_blocked_category_motor_vehicle(self):
        res = self.guard.verify_itc_eligibility("MOTOR_VEHICLE", 100000, 18000)
        assert res["verified"] is False

    def test_personal_consumption_blocked(self):
        res = self.guard.verify_itc_eligibility("personal expense", 500, 90)
        assert res["verified"] is False
        assert "personal consumption" in res["reason"]

    def test_eligible_expense(self):
        res = self.guard.verify_itc_eligibility("office supplies", 1000, 180)
        assert res["verified"] is True
        assert res["eligible_itc"] == 180

    def test_gift_below_threshold_allowed(self):
        res = self.guard.verify_itc_eligibility("gift to employee", 30000, 5400)
        assert res["verified"] is True
        assert res["eligible_itc"] == 5400

    def test_gift_above_threshold_blocked(self):
        res = self.guard.verify_itc_eligibility("gift to employee", 60000, 10800)
        assert res["verified"] is False

    def test_gstin_valid(self):
        res = self.guard.verify_gstin_format("22AAAAA0000A1Z5")
        assert res["verified"] is True

    def test_gstin_invalid(self):
        res = self.guard.verify_gstin_format("INVALID")
        assert res["verified"] is False
        assert "Invalid GSTIN" in res["error"]


# ------------------------------------------------------------------
# Form1099Guard — filing requirements
# ------------------------------------------------------------------

from qwed_tax.jurisdictions.us.form1099_guard import Form1099Guard
from qwed_tax.models import ContractorPayment, PaymentType
from decimal import Decimal


class TestForm1099Guard:
    def setup_method(self):
        self.guard = Form1099Guard()

    def test_nec_above_threshold(self):
        payment = ContractorPayment(
            contractor_id="C001",
            payment_type=PaymentType.NON_EMPLOYEE_COMPENSATION,
            amount=Decimal("700.00"),
            calendar_year=2024
        )
        res = self.guard.verify_filing_requirement(payment)
        assert res["filing_required"] is True
        assert res["form"] == "1099-NEC"

    def test_nec_below_threshold(self):
        payment = ContractorPayment(
            contractor_id="C002",
            payment_type=PaymentType.NON_EMPLOYEE_COMPENSATION,
            amount=Decimal("500.00"),
            calendar_year=2024
        )
        res = self.guard.verify_filing_requirement(payment)
        assert res["filing_required"] is False

    def test_rent_above_threshold(self):
        payment = ContractorPayment(
            contractor_id="C003",
            payment_type=PaymentType.RENT,
            amount=Decimal("600.00"),
            calendar_year=2024
        )
        res = self.guard.verify_filing_requirement(payment)
        assert res["filing_required"] is True
        assert res["form"] == "1099-MISC"

    def test_royalty_above_threshold(self):
        payment = ContractorPayment(
            contractor_id="C004",
            payment_type=PaymentType.ROYALTIES,
            amount=Decimal("15.00"),
            calendar_year=2024
        )
        res = self.guard.verify_filing_requirement(payment)
        assert res["filing_required"] is True

    def test_royalty_below_threshold(self):
        payment = ContractorPayment(
            contractor_id="C005",
            payment_type=PaymentType.ROYALTIES,
            amount=Decimal("5.00"),
            calendar_year=2024
        )
        res = self.guard.verify_filing_requirement(payment)
        assert res["filing_required"] is False

    def test_attorney_above_threshold(self):
        payment = ContractorPayment(
            contractor_id="C006",
            payment_type=PaymentType.ATTORNEY_FEES,
            amount=Decimal("1000.00"),
            calendar_year=2024
        )
        res = self.guard.verify_filing_requirement(payment)
        assert res["filing_required"] is True
        assert res["form"] == "1099-MISC"


# ------------------------------------------------------------------
# TaxPreFlight — audit_transaction extracted methods
# ------------------------------------------------------------------

from qwed_tax.verifier import TaxPreFlight


class TestTaxPreFlightAudit:
    def setup_method(self):
        self.pf = TaxPreFlight()

    def test_empty_intent_passes(self):
        """No matching keys → nothing blocked."""
        report = self.pf.audit_transaction({})
        assert report["allowed"] is True
        assert report["blocks"] == []

    def test_capital_gains_missing_dates_keys(self):
        """intent has dates dict but missing buy/sell → block with message."""
        report = self.pf.audit_transaction({
            "asset_type": "equity",
            "dates": {}
        })
        assert report["allowed"] is False
        assert any("buy and sell dates" in b for b in report["blocks"])

    def test_expense_itc_blocked(self):
        """Blocked expense category → allowed=False."""
        report = self.pf.audit_transaction({
            "expense_category": "FOOD_AND_BEVERAGE",
            "amount": 5000,
            "tax_paid": 900
        })
        assert report["allowed"] is False

    def test_expense_itc_eligible(self):
        """Eligible category → allowed remains True."""
        report = self.pf.audit_transaction({
            "expense_category": "office_supplies",
            "amount": 1000,
            "tax_paid": 180
        })
        assert report["allowed"] is True

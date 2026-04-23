"""Tests covering new and changed code paths for guard coverage."""

from decimal import Decimal

from qwed_tax.guards.dtaa_guard import DTAAGuard
from qwed_tax.guards.indirect_tax_guard import InputCreditGuard
from qwed_tax.jurisdictions.us.form1099_guard import Form1099Guard
from qwed_tax.models import ContractorPayment, PaymentType
from qwed_tax.verifier import TaxPreFlight


# ------------------------------------------------------------------
# DTAAGuard - treaty rate logic
# ------------------------------------------------------------------


class TestDTAAGuard:
    def setup_method(self):
        self.guard = DTAAGuard()

    def test_ftc_without_treaty_rate(self):
        """No treaty rate means simple min(foreign_tax, home_tax)."""
        res = self.guard.verify_foreign_tax_credit(1000, 100, 30.0)
        assert res["allowable_credit"] == 100.0
        assert res["excess_tax_lapsed"] == 0.0

    def test_ftc_capped_by_home_tax(self):
        """Foreign tax above home tax is capped at the home liability."""
        res = self.guard.verify_foreign_tax_credit(1000, 200, 15.0)
        assert res["allowable_credit"] == 150.0
        assert res["excess_tax_lapsed"] == 50.0
        assert "FTC Capped" in res["message"]

    def test_ftc_with_treaty_rate_caps(self):
        """Treaty rate cap applies before the home-tax cap."""
        res = self.guard.verify_foreign_tax_credit(
            1000, 200, 30.0, foreign_tax_limit_rate=10.0
        )
        assert res["allowable_credit"] == 100.0
        assert res["excess_tax_lapsed"] == 100.0
        assert "Treaty" in res["message"]

    def test_ftc_treaty_rate_no_effect_when_generous(self):
        """Generous treaty rate should not reduce an already valid full credit."""
        res = self.guard.verify_foreign_tax_credit(
            1000, 100, 30.0, foreign_tax_limit_rate=50.0
        )
        assert res["allowable_credit"] == 100.0
        assert res["excess_tax_lapsed"] == 0.0


# ------------------------------------------------------------------
# InputCreditGuard - ITC eligibility + GSTIN
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

    def test_gift_at_threshold_blocked(self):
        """Gift at exactly 50,000 should be blocked because the rule is amount < 50,000."""
        res = self.guard.verify_itc_eligibility("gift to employee", 50000, 9000)
        assert res["verified"] is False

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
# Form1099Guard - filing requirements
# ------------------------------------------------------------------


class TestForm1099Guard:
    def setup_method(self):
        self.guard = Form1099Guard()

    def test_nec_above_threshold(self):
        payment = ContractorPayment(
            contractor_id="C001",
            payment_type=PaymentType.NON_EMPLOYEE_COMPENSATION,
            amount=Decimal("700.00"),
            calendar_year=2024,
        )
        res = self.guard.verify_filing_requirement(payment)
        assert res["filing_required"] is True
        assert res["form"] == "1099-NEC"

    def test_nec_below_threshold(self):
        payment = ContractorPayment(
            contractor_id="C002",
            payment_type=PaymentType.NON_EMPLOYEE_COMPENSATION,
            amount=Decimal("500.00"),
            calendar_year=2024,
        )
        res = self.guard.verify_filing_requirement(payment)
        assert res["filing_required"] is False

    def test_rent_above_threshold(self):
        payment = ContractorPayment(
            contractor_id="C003",
            payment_type=PaymentType.RENT,
            amount=Decimal("600.00"),
            calendar_year=2024,
        )
        res = self.guard.verify_filing_requirement(payment)
        assert res["filing_required"] is True
        assert res["form"] == "1099-MISC"

    def test_royalty_above_threshold(self):
        payment = ContractorPayment(
            contractor_id="C004",
            payment_type=PaymentType.ROYALTIES,
            amount=Decimal("15.00"),
            calendar_year=2024,
        )
        res = self.guard.verify_filing_requirement(payment)
        assert res["filing_required"] is True

    def test_royalty_below_threshold(self):
        payment = ContractorPayment(
            contractor_id="C005",
            payment_type=PaymentType.ROYALTIES,
            amount=Decimal("5.00"),
            calendar_year=2024,
        )
        res = self.guard.verify_filing_requirement(payment)
        assert res["filing_required"] is False

    def test_attorney_above_threshold(self):
        payment = ContractorPayment(
            contractor_id="C006",
            payment_type=PaymentType.ATTORNEY_FEES,
            amount=Decimal("1000.00"),
            calendar_year=2024,
        )
        res = self.guard.verify_filing_requirement(payment)
        assert res["filing_required"] is True
        assert res["form"] == "1099-MISC"


# ------------------------------------------------------------------
# TaxPreFlight - fail-closed action orchestration
# ------------------------------------------------------------------


class TestTaxPreFlightAudit:
    def setup_method(self):
        self.pf = TaxPreFlight()

    def test_empty_intent_blocks(self):
        """Empty payloads must fail closed instead of silently passing."""
        report = self.pf.audit_transaction({})
        assert report["allowed"] is False
        assert report["checks_run"] == []
        assert "non-empty intent payload" in report["blocks"][0]

    def test_missing_action_blocks_even_with_claim_data(self):
        """Action is mandatory so sparse payloads cannot silently skip checks."""
        report = self.pf.audit_transaction(
            {
                "expense_category": "office_supplies",
                "amount": 1000,
                "tax_paid": 180,
            }
        )
        assert report["allowed"] is False
        assert report["checks_run"] == []
        assert "requires a supported action" in report["blocks"][0]

    def test_unknown_action_blocks(self):
        """Unsupported actions must not fall back to an allow result."""
        report = self.pf.audit_transaction(
            {
                "action": "magic_tax_mode",
                "expense_category": "office_supplies",
                "amount": 1000,
                "tax_paid": 180,
            }
        )
        assert report["allowed"] is False
        assert report["checks_run"] == []
        assert "supported action" in report["blocks"][0]

    def test_hire_action_with_misnamed_keys_blocks(self):
        """Typos in required keys must block instead of skipping classification."""
        report = self.pf.audit_transaction(
            {
                "action": "hire",
                "worker_type": "1099",
                "workerFacts": {
                    "provides_tools": True,
                    "reimburses_expenses": True,
                    "indefinite_relationship": True,
                },
            }
        )
        assert report["allowed"] is False
        assert report["checks_run"] == []
        assert "worker_facts.provides_tools" in report["blocks"][0]

    def test_trade_tax_capital_gains_missing_nested_dates_block(self):
        """Nested required fields must be present before capital gains runs."""
        report = self.pf.audit_transaction(
            {
                "action": "trade_tax",
                "asset_type": "equity",
                "dates": {},
                "claimed_rate": "10%",
            }
        )
        assert report["allowed"] is False
        assert report["checks_run"] == []
        assert "dates.buy" in report["blocks"][0]
        assert "dates.sell" in report["blocks"][0]

    def test_expense_claim_blocked_category_returns_failed_check(self):
        """A valid action shape should run the relevant check and surface the block."""
        report = self.pf.audit_transaction(
            {
                "action": "expense_claim",
                "expense_category": "FOOD_AND_BEVERAGE",
                "amount": 5000,
                "tax_paid": 900,
            }
        )
        assert report["allowed"] is False
        assert report["checks_run"] == ["expense_itc"]
        assert "ITC is blocked" in report["blocks"][0]

    def test_expense_claim_eligible_runs_and_stays_allowed(self):
        """A complete supported claim should run one check and remain allowed."""
        report = self.pf.audit_transaction(
            {
                "action": "expense_claim",
                "expense_category": "office_supplies",
                "amount": 1000,
                "tax_paid": 180,
            }
        )
        assert report["allowed"] is True
        assert report["checks_run"] == ["expense_itc"]
        assert report["blocks"] == []

    def test_economic_nexus_violation_runs_and_blocks(self):
        """Economic nexus claims should run and block when thresholds are crossed."""
        report = self.pf.audit_transaction(
            {
                "action": "economic_nexus",
                "state": "NY",
                "sales_data": {"amount": 500001, "transactions": 10},
                "tax_decision": "no_tax",
            }
        )
        assert report["allowed"] is False
        assert report["checks_run"] == ["economic_nexus"]
        assert "Nexus Violation" in report["blocks"][0]

    def test_trade_tax_setoff_runs_and_blocks_illegal_offset(self):
        """Trade tax set-off claims should block speculative loss misuse."""
        report = self.pf.audit_transaction(
            {
                "action": "trade_tax",
                "loss_head": "intraday loss",
                "loss_amount": 2500,
                "offset_head": "futures profit",
            }
        )
        assert report["allowed"] is False
        assert report["checks_run"] == ["trader_setoff"]
        assert "Illegal Set-Off" in report["blocks"][0]

    def test_trade_tax_capital_gains_runs_and_blocks_rate_mismatch(self):
        """Capital gains claims should run and block incorrect statutory rates."""
        report = self.pf.audit_transaction(
            {
                "action": "trade_tax",
                "asset_type": "equity",
                "dates": {"buy": "2022-01-01", "sell": "2024-02-01"},
                "claimed_rate": "10%",
            }
        )
        assert report["allowed"] is False
        assert report["checks_run"] == ["capital_gains"]
        assert "Rate Mismatch" in report["blocks"][0]

    def test_corporate_action_loan_check_runs_and_blocks(self):
        """Corporate loan compliance should block prohibited borrower roles."""
        report = self.pf.audit_transaction(
            {
                "action": "corporate_action",
                "lender_type": "company",
                "borrower_role": "director",
                "interest_rate": 10.0,
                "market_rate": 8.0,
            }
        )
        assert report["allowed"] is False
        assert report["checks_run"] == ["corporate_loans"]
        assert "Section 185" in report["blocks"][0]

    def test_corporate_action_unsupported_startup_claim_blocks_without_fake_success(self):
        """Unsupported startup valuation rounds must fail closed instead of pretending to verify."""
        report = self.pf.audit_transaction(
            {
                "action": "corporate_action",
                "investment_round": "series_a",
                "investment_amount": "100000",
                "cap_price": "8",
                "discount": "0.2",
                "next_round_price": "10",
            }
        )
        assert report["allowed"] is False
        assert report["checks_run"] == []
        assert "did not include a complete verifiable claim" in report["blocks"][0]
        assert "startup_valuation" in report["blocks"][0]

    def test_remittance_limit_violation_runs_and_blocks(self):
        """Remittance checks should block when annual limit is exceeded."""
        report = self.pf.audit_transaction(
            {
                "action": "remit_money",
                "remittance_amount_usd": 10000,
                "purpose": "education",
                "fy_usage": 245001,
            }
        )
        assert report["allowed"] is False
        assert report["checks_run"] == ["international_remittance"]
        assert "exceeds LRS limit" in report["blocks"][0]

    def test_hire_action_runs_and_blocks_misclassification(self):
        """Once required fields are present, the derived classification should gate allow."""
        report = self.pf.audit_transaction(
            {
                "action": "hire",
                "worker_type": "1099",
                "worker_facts": {
                    "provides_tools": True,
                    "reimburses_expenses": True,
                    "indefinite_relationship": True,
                },
            }
        )
        assert report["allowed"] is False
        assert report["checks_run"] == ["worker_classification"]
        assert "Misclassification Risk" in report["blocks"][0]

"""Tests covering new and changed code paths for guard coverage."""

from decimal import Decimal

from qwed_tax.guards.nexus_guard import NexusGuard
from qwed_tax.guards.related_party_guard import RelatedPartyGuard
from qwed_tax.guards.remittance_guard import RemittanceGuard
from qwed_tax.guards.speculation_guard import SpeculationGuard
from qwed_tax.guards.tds_guard import TDSGuard
from qwed_tax.guards.transfer_pricing_guard import TransferPricingGuard
from qwed_tax.guards.dtaa_guard import DTAAGuard
from qwed_tax.guards.indirect_tax_guard import InputCreditGuard
from qwed_tax.jurisdictions.us.form1099_guard import Form1099Guard
from qwed_tax.jurisdictions.us.withholding_guard import W4Form, WithholdingGuard
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
        # Trailing zeros are preserved from Decimal arithmetic; keep this exact string shape intentional.
        res = self.guard.verify_foreign_tax_credit(1000, 100, 30.0)
        assert res["allowable_credit"] == "100"
        assert res["excess_tax_lapsed"] == "0"

    def test_ftc_capped_by_home_tax(self):
        """Foreign tax above home tax is capped at the home liability."""
        res = self.guard.verify_foreign_tax_credit(1000, 200, 15.0)
        assert res["allowable_credit"] == "150.00"
        assert res["excess_tax_lapsed"] == "50.00"
        assert "FTC Capped" in res["message"]

    def test_ftc_with_treaty_rate_caps(self):
        """Treaty rate cap applies before the home-tax cap."""
        # Treaty-rate arithmetic preserves a Decimal exponent here, so "100.0" is expected and intentional.
        res = self.guard.verify_foreign_tax_credit(
            1000, 200, 30.0, foreign_tax_limit_rate=10.0
        )
        assert res["allowable_credit"] == "100.0"
        assert res["excess_tax_lapsed"] == "100.0"
        assert "Treaty" in res["message"]

    def test_ftc_treaty_rate_no_effect_when_generous(self):
        """Generous treaty rate should not reduce an already valid full credit."""
        res = self.guard.verify_foreign_tax_credit(
            1000, 100, 30.0, foreign_tax_limit_rate=50.0
        )
        assert res["allowable_credit"] == "100"
        assert res["excess_tax_lapsed"] == "0"

    def test_ftc_invalid_numeric_input_blocks(self):
        """FTC verification should fail closed on invalid numeric input."""
        res = self.guard.verify_foreign_tax_credit("pending", 100, 30.0)
        assert res["verified"] is False
        assert res["allowable_credit"] == "0"
        assert "foreign_income must be a numeric value." == res["message"]

    def test_ftc_negative_inputs_block(self):
        """FTC verification should fail closed on negative financial inputs."""
        res = self.guard.verify_foreign_tax_credit(-1000, 100, 30.0)
        assert res["verified"] is False
        assert res["message"] == "foreign_income must be a non-negative numeric value."


# ------------------------------------------------------------------
# InputCreditGuard - ITC eligibility + GSTIN
# ------------------------------------------------------------------


class TestInputCreditGuard:
    def setup_method(self):
        self.guard = InputCreditGuard()

    def test_blocked_category_food(self):
        res = self.guard.verify_itc_eligibility("food and beverage", 5000, 900)
        assert res["verified"] is False
        assert res["eligible_itc"] == "0"

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
        assert res["eligible_itc"] == "180"

    def test_gift_below_threshold_allowed(self):
        res = self.guard.verify_itc_eligibility("gift to employee", 30000, 5400)
        assert res["verified"] is True
        assert res["eligible_itc"] == "5400"

    def test_gift_at_threshold_allowed(self):
        """Gift at exactly 50,000 remains eligible; only values above that block."""
        res = self.guard.verify_itc_eligibility("gift to employee", 50000, 9000)
        assert res["verified"] is True
        assert res["eligible_itc"] == "9000"

    def test_gift_above_threshold_blocked(self):
        res = self.guard.verify_itc_eligibility("gift to employee", 60000, 10800)
        assert res["verified"] is False

    def test_gstin_valid(self):
        # Real-world GSTIN with a correct base-36 check digit.
        res = self.guard.verify_gstin_format("27AAPFU0939F1ZV")
        assert res["verified"] is True

    def test_gstin_invalid(self):
        res = self.guard.verify_gstin_format("INVALID")
        assert res["verified"] is False
        assert "Invalid GSTIN" in res["error"]

    def test_gstin_valid_format_wrong_checksum(self):
        # Matches the structural pattern but the 15th check digit is wrong.
        # The error stays generic on purpose (no correct-digit disclosure).
        res = self.guard.verify_gstin_format("22AAAAA0000A1Z5")
        assert res["verified"] is False
        assert "checksum" in res["error"]
        # The correct check digit must NOT be echoed back (anti-oracle).
        assert "'C'" not in res["error"]

    def test_invalid_numeric_itc_input_blocks(self):
        res = self.guard.verify_itc_eligibility("office supplies", "pending", 180)
        assert res["verified"] is False
        assert res["eligible_itc"] == "0"
        assert res["reason"] == "amount must be a numeric value."


# ------------------------------------------------------------------
# Financial guard numeric safety - Decimal boundary parsing
# ------------------------------------------------------------------


class TestFinancialGuardNumericSafety:
    def test_speculation_blocks_invalid_loss_amount(self):
        guard = SpeculationGuard()
        res = guard.verify_setoff("intraday loss", "pending", "futures profit")
        assert res["verified"] is False
        assert res["error"] == "loss_amount must be a numeric value."

    def test_nexus_blocks_invalid_sales_amount(self):
        guard = NexusGuard()
        res = guard.check_nexus_liability("CA", "pending", 5, "no_tax")
        assert res["verified"] is False
        assert res["error"] == "ytd_sales must be a numeric value."

    def test_related_party_accepts_decimal_string_rates(self):
        guard = RelatedPartyGuard()
        res = guard.verify_loan_compliance("company", "employee", "8.25", "8.00")
        assert res["verified"] is True

    def test_transfer_pricing_returns_string_adjustment(self):
        guard = TransferPricingGuard()
        res = guard.verify_arms_length_price("105", "100", tolerance_percent="3.0")
        assert res["verified"] is False
        assert res["potential_adjustment"] == "-5"
        assert res["safe_harbour_range"] == ["97.00", "103.00"]

    def test_transfer_pricing_within_range_uses_consistent_shape(self):
        guard = TransferPricingGuard()
        res = guard.verify_arms_length_price("102", "100", tolerance_percent="3.0")
        assert res["verified"] is True
        assert res["potential_adjustment"] == "0"
        assert res["safe_harbour_range"] == ["97.00", "103.00"]

    def test_transfer_pricing_blocks_invalid_numeric_input(self):
        guard = TransferPricingGuard()
        res = guard.verify_arms_length_price("draft", "100", tolerance_percent="3.0")
        assert res["verified"] is False
        assert res["risk"] == "INVALID_NUMERIC_INPUT"
        assert res["message"] == "transaction_price must be a numeric value."

    def test_remittance_tcs_accepts_string_amount(self):
        guard = RemittanceGuard()
        tcs = guard.calculate_tcs("900000", "education", is_loan_funded=False)
        assert tcs == Decimal("10000")

    def test_tds_blocks_non_finite_values(self):
        guard = TDSGuard()
        res = guard.calculate_deduction("PROFESSIONAL_FEES", float("inf"), 0)
        assert res["verified"] is False
        assert res["error"] == "invoice_amount must be a finite numeric value."


# ------------------------------------------------------------------
# WithholdingGuard - exact Decimal W-4 inputs
# ------------------------------------------------------------------


class TestWithholdingGuard:
    def setup_method(self):
        self.guard = WithholdingGuard()

    def test_exempt_status_accepts_decimal_liability(self):
        form = W4Form(
            employee_id="E001",
            claim_exempt=True,
            tax_liability_last_year=Decimal("0"),
            expect_refund_this_year=True,
        )
        res = self.guard.verify_exempt_status(form)
        assert res["verified"] is True

    def test_exempt_status_blocks_decimal_liability(self):
        form = W4Form(
            employee_id="E002",
            claim_exempt=True,
            tax_liability_last_year=Decimal("1.25"),
            expect_refund_this_year=True,
        )
        res = self.guard.verify_exempt_status(form)
        assert res["verified"] is False

    def test_w4_form_rejects_boolean_tax_liability(self):
        try:
            W4Form(
                employee_id="E003",
                claim_exempt=True,
                tax_liability_last_year=True,
                expect_refund_this_year=True,
            )
        except ValueError as exc:
            assert "tax_liability_last_year must be a numeric value." in str(exc)
        else:
            raise AssertionError("W4Form should reject boolean tax liability values.")


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

    def test_healthcare_unmodeled_filing_required_is_unverifiable(self):
        """HEALTHCARE is a valid enum value with no filing rule — must not default to False."""
        payment = ContractorPayment(
            contractor_id="C007",
            payment_type=PaymentType.HEALTHCARE,
            amount=Decimal("5000.00"),
            calendar_year=2024,
        )
        res = self.guard.verify_filing_requirement(payment)
        assert res["filing_required"] == "UNVERIFIABLE"
        assert res["form"] is None
        assert "manual determination required" in res["reason"]


# ------------------------------------------------------------------
# TaxPreFlight - fail-closed action orchestration
# ------------------------------------------------------------------


class TestTaxPreFlightAudit:
    def setup_method(self):
        self.pf = TaxPreFlight()

    def test_non_dict_intents_block(self):
        """Non-dict payloads must fail closed with a consistent report shape."""
        for bad_intent in (None, [], "bad"):
            report = self.pf.audit_transaction(bad_intent)
            assert report["allowed"] is False
            assert report["action"] is None
            assert report["checks_run"] == []
            assert "non-empty intent payload" in report["blocks"][0]

    def test_empty_intent_blocks(self):
        """Empty payloads must fail closed instead of silently passing."""
        report = self.pf.audit_transaction({})
        assert report["allowed"] is False
        assert report["action"] is None
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
        assert report["action"] is None
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
        assert report["action"] == "magic_tax_mode"
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
                "loss_head": "intraday",
                "loss_amount": 2500,
                "offset_head": "futures",
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

    def test_trade_tax_stray_loss_key_does_not_select_wrong_check(self):
        """Capital gains payloads should not co-select trader_setoff from a stray key."""
        report = self.pf.audit_transaction(
            {
                "action": "trade_tax",
                "asset_type": "equity",
                "dates": {"buy": "2022-01-01", "sell": "2024-02-01"},
                "claimed_rate": "10%",
                "loss_head": "intraday loss",
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

    def test_remittance_non_numeric_values_block_without_crashing(self):
        """Remittance checks must fail closed on non-numeric values."""
        report = self.pf.audit_transaction(
            {
                "action": "remit_money",
                "remittance_amount_usd": "pending",
                "purpose": "education",
                "fy_usage": "unknown",
            }
        )
        assert report["allowed"] is False
        assert report["checks_run"] == ["international_remittance"]
        assert "numeric value" in report["blocks"][0]

    def test_remittance_non_finite_values_block_without_crashing(self):
        """Remittance checks must fail closed on NaN/Infinity values."""
        report = self.pf.audit_transaction(
            {
                "action": "remit_money",
                "remittance_amount_usd": float("inf"),
                "purpose": "education",
                "fy_usage": float("nan"),
            }
        )
        assert report["allowed"] is False
        assert report["checks_run"] == ["international_remittance"]
        assert "finite numeric value" in report["blocks"][0]

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

    def test_pay_invoice_tds_requirement_blocks_and_adds_advisory(self):
        """Invoice payments should block until required TDS is deducted."""
        report = self.pf.audit_transaction(
            {
                "action": "pay_invoice",
                "service_type": "professional_fees",
                "amount": 50000,
                "ytd_payment": 0,
            }
        )
        assert report["allowed"] is False
        assert report["checks_run"] == ["invoice_tds"]
        assert "advisories" in report
        assert "TDS Required" in report["advisories"][0]
        assert "requires TDS deduction" in report["blocks"][0]

    def test_pay_invoice_non_numeric_values_block_without_crashing(self):
        """Pay-invoice checks must fail closed on non-numeric values."""
        report = self.pf.audit_transaction(
            {
                "action": "pay_invoice",
                "service_type": "professional_fees",
                "amount": "pending",
                "ytd_payment": "carry_forward",
            }
        )
        assert report["allowed"] is False
        assert report["checks_run"] == ["invoice_tds"]
        assert "numeric value" in report["blocks"][0]

    def test_pay_invoice_non_finite_values_block_without_crashing(self):
        """Pay-invoice checks must fail closed on NaN/Infinity values."""
        report = self.pf.audit_transaction(
            {
                "action": "pay_invoice",
                "service_type": "professional_fees",
                "amount": float("nan"),
                "ytd_payment": float("inf"),
            }
        )
        assert report["allowed"] is False
        assert report["checks_run"] == ["invoice_tds"]
        assert "finite numeric value" in report["blocks"][0]

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


# ------------------------------------------------------------------
# Issue #16: Fail-closed on unknown/unmodeled tax rules
# ------------------------------------------------------------------


class TestIssue16FailClosedUnknownRules:
    """Each guard must fail closed when it encounters an unknown rule, category, state, or type."""

    def test_tds_unknown_service_type_blocks(self):
        """TDSGuard must not return verified=True for unmapped service types."""
        guard = TDSGuard()
        res = guard.calculate_deduction("UNKNOWN_SERVICE", 50000, 0)
        assert res["verified"] is False
        assert "No TDS rule configured" in res["error"]
        assert "deduction" not in res

    def test_capital_gains_unknown_asset_type_blocks(self):
        """CapitalGainsGuard must not return verified=True for unmapped asset/term combos."""
        from qwed_tax.guards.capital_gains_guard import CapitalGainsGuard
        guard = CapitalGainsGuard()
        res = guard.verify_tax_rate("gold", "LTCG", "10%")
        assert res["verified"] is False
        assert "No statutory rate configured" in res["error"]

    def test_capital_gains_known_rate_still_passes(self):
        """Known asset/term must still verify correctly — no regression."""
        from qwed_tax.guards.capital_gains_guard import CapitalGainsGuard
        guard = CapitalGainsGuard()
        res = guard.verify_tax_rate("equity", "LTCG", "12.5%")
        assert res["verified"] is True

    def test_nexus_unknown_state_blocks(self):
        """NexusGuard must not return verified=True for unlisted states."""
        guard = NexusGuard()
        res = guard.check_nexus_liability("WA", 900000, 500, "no_tax")
        assert res["verified"] is False
        assert "not in configured nexus threshold table" in res["error"]

    def test_nexus_known_state_still_passes(self):
        """Known state with no nexus violation must still pass — no regression."""
        guard = NexusGuard()
        res = guard.check_nexus_liability("CA", 100, 0, "no_tax")
        assert res["verified"] is True

    def test_address_unknown_state_blocks(self):
        """AddressGuard must not return verified=True for unlisted states."""
        from qwed_tax.address_guard import AddressGuard
        from qwed_tax.models import Address, State
        guard = AddressGuard()
        addr = Address(street="123 Main St", city="Baltimore", state=State.MD, zip_code="21201")
        res = guard.verify_address(addr)
        assert res["verified"] is False
        assert "manual review required" in res["message"]

    def test_address_known_state_still_passes(self):
        """Known state with matching zip prefix must still pass — no regression."""
        from qwed_tax.address_guard import AddressGuard
        from qwed_tax.models import Address, State
        guard = AddressGuard()
        addr = Address(street="123 Main St", city="New York", state=State.NY, zip_code="10001")
        res = guard.verify_address(addr)
        assert res["verified"] is True


# ------------------------------------------------------------------
# Issue #17 + #18: Classification, SLAB, Speculation, Crypto, Setoff
# ------------------------------------------------------------------


class TestIssue17ClassificationAmbiguity:
    """ClassificationGuard mixed-signal detection and claim type guard."""

    def test_mixed_signals_blocks(self):
        """Two employee indicators but not all three → ambiguous → block."""
        from qwed_tax.guards.classification_guard import ClassificationGuard
        guard = ClassificationGuard()
        res = guard.verify_classification_claim(
            "1099",
            {"provides_tools": False, "reimburses_expenses": True, "indefinite_relationship": True},
        )
        assert res["verified"] is False
        assert "Ambiguous" in res["error"]

    def test_clear_contractor_passes(self):
        """No employee indicators → contractor is safe."""
        from qwed_tax.guards.classification_guard import ClassificationGuard
        guard = ClassificationGuard()
        res = guard.verify_classification_claim(
            "1099",
            {"provides_tools": False, "reimburses_expenses": False, "indefinite_relationship": False},
        )
        assert res["verified"] is True

    def test_non_string_claim_blocks(self):
        """Non-string llm_claim must fail closed, not crash."""
        from qwed_tax.guards.classification_guard import ClassificationGuard
        guard = ClassificationGuard()
        res = guard.verify_classification_claim(123, {"provides_tools": False, "reimburses_expenses": False, "indefinite_relationship": False})
        assert res["verified"] is False
        assert "non-empty string" in res["error"]


class TestIssue17CapitalGainsDebtFundAndSlab:
    """CapitalGainsGuard debt_fund always-STCG + SLAB fail-closed."""

    def test_debt_fund_always_stcg(self):
        """debt_fund must always return STCG regardless of holding period."""
        from qwed_tax.guards.capital_gains_guard import CapitalGainsGuard
        guard = CapitalGainsGuard()
        term = guard.determine_term("2020-01-01", "2025-01-01", "debt_fund")
        assert term == "STCG"

    def test_debt_fund_stcg_short_holding(self):
        """debt_fund with short holding also STCG."""
        from qwed_tax.guards.capital_gains_guard import CapitalGainsGuard
        guard = CapitalGainsGuard()
        term = guard.determine_term("2024-01-01", "2024-06-01", "debt_fund")
        assert term == "STCG"

    def test_unknown_asset_raises(self):
        """Unknown asset type must raise ValueError."""
        from qwed_tax.guards.capital_gains_guard import CapitalGainsGuard
        guard = CapitalGainsGuard()
        import pytest
        with pytest.raises(ValueError, match="Unknown asset type"):
            guard.determine_term("2020-01-01", "2021-01-01", "gold")

    def test_slab_rate_blocks(self):
        """SLAB rate must return verified=False — cannot verify without income bracket."""
        from qwed_tax.guards.capital_gains_guard import CapitalGainsGuard
        guard = CapitalGainsGuard()
        res = guard.verify_tax_rate("debt", "LTCG", "10%")
        assert res["verified"] is False
        assert "slab" in res["error"].lower()

    def test_bad_date_raises(self):
        """Bad date format must raise ValueError."""
        from qwed_tax.guards.capital_gains_guard import CapitalGainsGuard
        guard = CapitalGainsGuard()
        import pytest
        with pytest.raises(ValueError, match="Invalid date format"):
            guard.determine_term("not-a-date", "2021-01-01", "equity")


class TestIssue17SpeculationExactMatch:
    """SpeculationGuard must use exact match, not substring."""

    def test_known_intraday_classified_speculative(self):
        from qwed_tax.guards.speculation_guard import SpeculationGuard
        guard = SpeculationGuard()
        res = guard.verify_setoff("intraday", 5000, "f&o")
        assert res["verified"] is False

    def test_unknown_source_blocks(self):
        from qwed_tax.guards.speculation_guard import SpeculationGuard
        guard = SpeculationGuard()
        res = guard.verify_setoff("intraday_equity_position", 5000, "f&o")
        assert res["verified"] is False
        assert "Unrecognized" in res["error"]

    def test_composed_string_with_business_blocks(self):
        """String containing 'business' but not an exact match must block."""
        from qwed_tax.guards.speculation_guard import SpeculationGuard
        guard = SpeculationGuard()
        res = guard.verify_setoff("side_business_income", 5000, "delivery")
        assert res["verified"] is False
        assert "Unrecognized" in res["error"]

    def test_delivery_vs_delivery_allowed(self):
        """Known non-speculative vs non-speculative is allowed."""
        from qwed_tax.guards.speculation_guard import SpeculationGuard
        guard = SpeculationGuard()
        res = guard.verify_setoff("delivery", 5000, "f&o")
        assert res["verified"] is True


class TestIssue18CryptoZeroNegative:
    """CryptoTaxGuard zero vs negative income distinction."""

    def test_zero_income_zero_tax_verified(self):
        from qwed_tax.jurisdictions.india.guards.crypto_guard import CryptoTaxGuard
        from decimal import Decimal
        guard = CryptoTaxGuard()
        res = guard.verify_flat_tax_rate(Decimal("0"), Decimal("0"))
        assert res.verified is True

    def test_zero_income_nonzero_tax_blocked(self):
        from qwed_tax.jurisdictions.india.guards.crypto_guard import CryptoTaxGuard
        from decimal import Decimal
        guard = CryptoTaxGuard()
        res = guard.verify_flat_tax_rate(Decimal("0"), Decimal("500"))
        assert res.verified is False
        assert "zero" in res.message.lower()

    def test_negative_income_blocked(self):
        from qwed_tax.jurisdictions.india.guards.crypto_guard import CryptoTaxGuard
        from decimal import Decimal
        guard = CryptoTaxGuard()
        res = guard.verify_flat_tax_rate(Decimal("-5000"), Decimal("0"))
        assert res.verified is False
        assert "loss" in res.message.lower()


class TestIssue17SetoffAllowlist:
    """SetoffGuard allowlist — unknown heads blocked."""

    def test_salary_loss_blocked(self):
        """Salary losses cannot be set off inter-head."""
        from qwed_tax.jurisdictions.india.guards.setoff_guard import InterHeadAdjustmentGuard, TaxHead
        guard = InterHeadAdjustmentGuard()
        res = guard.verify_setoff(TaxHead.SALARY, TaxHead.BUSINESS_NON_SPECULATIVE)
        assert res["verified"] is False

    def test_known_allowed_head_passes(self):
        """House property loss can be set off against business profit."""
        from qwed_tax.jurisdictions.india.guards.setoff_guard import InterHeadAdjustmentGuard, TaxHead
        guard = InterHeadAdjustmentGuard()
        res = guard.verify_setoff(TaxHead.HOUSE_PROPERTY, TaxHead.BUSINESS_NON_SPECULATIVE)
        assert res["verified"] is True

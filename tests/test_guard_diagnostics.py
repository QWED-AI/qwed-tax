"""Tests for TaxDiagnosticResult migration of 9 guards (Issue #47)."""

import pytest
from decimal import Decimal

from qwed_tax.diagnostics import TaxDiagnosticResult, TaxDiagnosticStatus


class TestCapitalGainsGuardDiagnostic:
    def test_verified_ltcg(self):
        from qwed_tax.guards.capital_gains_guard import CapitalGainsGuard
        guard = CapitalGainsGuard()
        raw = guard.verify_tax_rate("equity", "LTCG", "12.5%")
        diag = CapitalGainsGuard.to_diagnostic(raw)
        assert diag.status is TaxDiagnosticStatus.VERIFIED
        assert diag.proof_ref is not None
        assert diag.proof_ref.startswith("sha256:")
        assert diag.developer_fields["constraint_id"] == "CG_EQUITY_LTCG_112A"

    def test_blocked_rate_mismatch(self):
        from qwed_tax.guards.capital_gains_guard import CapitalGainsGuard
        guard = CapitalGainsGuard()
        raw = guard.verify_tax_rate("equity", "LTCG", "10%")
        diag = CapitalGainsGuard.to_diagnostic(raw)
        assert diag.status is TaxDiagnosticStatus.BLOCKED
        assert diag.proof_ref is None
        assert "Rate Mismatch" in diag.developer_fields["error"]

    def test_unverifiable_no_rate(self):
        from qwed_tax.guards.capital_gains_guard import CapitalGainsGuard
        guard = CapitalGainsGuard()
        raw = guard.verify_tax_rate("unknown_asset", "LTCG", "10%")
        diag = CapitalGainsGuard.to_diagnostic(raw)
        assert diag.status is TaxDiagnosticStatus.UNVERIFIABLE
        assert diag.proof_ref is None
        assert diag.developer_fields["constraint_id"] == "CG_NO_RATE_CONFIGURED"

    def test_unverifiable_slab_rate(self):
        from qwed_tax.guards.capital_gains_guard import CapitalGainsGuard
        guard = CapitalGainsGuard()
        raw = guard.verify_tax_rate("debt", "LTCG", "20%")
        diag = CapitalGainsGuard.to_diagnostic(raw)
        assert diag.status is TaxDiagnosticStatus.UNVERIFIABLE
        assert diag.proof_ref is None
        assert "slab" in diag.developer_fields["error"].lower()

    def test_verified_without_audit_trace_raises(self):
        from qwed_tax.guards.capital_gains_guard import CapitalGainsGuard
        with pytest.raises(ValueError, match="audit_trace"):
            CapitalGainsGuard.to_diagnostic({"verified": True})


class TestClassificationGuardDiagnostic:
    def test_verified_contractor(self):
        from qwed_tax.guards.classification_guard import ClassificationGuard
        guard = ClassificationGuard()
        raw = guard.verify_classification_claim("1099", {
            "provides_tools": False,
            "reimburses_expenses": False,
            "indefinite_relationship": False,
        })
        diag = ClassificationGuard.to_diagnostic(raw)
        assert diag.status is TaxDiagnosticStatus.VERIFIED
        assert diag.proof_ref is not None
        assert diag.developer_fields["constraint_id"] == "IRS_COMMON_LAW"

    def test_blocked_misclassification(self):
        from qwed_tax.guards.classification_guard import ClassificationGuard
        guard = ClassificationGuard()
        raw = guard.verify_classification_claim("1099", {
            "provides_tools": True,
            "reimburses_expenses": True,
            "indefinite_relationship": True,
        })
        diag = ClassificationGuard.to_diagnostic(raw)
        assert diag.status is TaxDiagnosticStatus.BLOCKED
        assert diag.proof_ref is None
        assert "Misclassification" in diag.developer_fields["error"]

    def test_blocked_ambiguous(self):
        from qwed_tax.guards.classification_guard import ClassificationGuard
        guard = ClassificationGuard()
        raw = guard.verify_classification_claim("1099", {
            "provides_tools": True,
            "reimburses_expenses": False,
            "indefinite_relationship": False,
        })
        diag = ClassificationGuard.to_diagnostic(raw)
        assert diag.status is TaxDiagnosticStatus.UNVERIFIABLE
        assert "Ambiguous" in diag.developer_fields["error"]

    def test_verified_without_audit_trace_raises(self):
        from qwed_tax.guards.classification_guard import ClassificationGuard
        with pytest.raises(ValueError, match="audit_trace"):
            ClassificationGuard.to_diagnostic({"verified": True})


class TestSpeculationGuardDiagnostic:
    def test_verified_allowed_setoff(self):
        from qwed_tax.guards.speculation_guard import SpeculationGuard
        guard = SpeculationGuard()
        raw = guard.verify_setoff("f&o", "50000", "capital_gains")
        diag = SpeculationGuard.to_diagnostic(raw)
        assert diag.status is TaxDiagnosticStatus.VERIFIED
        assert diag.proof_ref is not None
        assert diag.developer_fields["constraint_id"] == "SPECULATIVE_43_5"

    def test_blocked_illegal_setoff(self):
        from qwed_tax.guards.speculation_guard import SpeculationGuard
        guard = SpeculationGuard()
        raw = guard.verify_setoff("intraday", "50000", "f&o")
        diag = SpeculationGuard.to_diagnostic(raw)
        assert diag.status is TaxDiagnosticStatus.BLOCKED
        assert diag.proof_ref is None
        assert "Illegal" in diag.developer_fields["error"]
        assert diag.developer_fields["fix"] is not None

    def test_blocked_unknown_source(self):
        from qwed_tax.guards.speculation_guard import SpeculationGuard
        guard = SpeculationGuard()
        raw = guard.verify_setoff("unknown", "50000", "f&o")
        diag = SpeculationGuard.to_diagnostic(raw)
        assert diag.status is TaxDiagnosticStatus.UNVERIFIABLE
        assert "Unrecognized" in diag.developer_fields["error"]

    def test_verified_without_audit_trace_raises(self):
        from qwed_tax.guards.speculation_guard import SpeculationGuard
        with pytest.raises(ValueError, match="audit_trace"):
            SpeculationGuard.to_diagnostic({"verified": True})


class TestInterHeadAdjustmentGuardDiagnostic:
    def test_verified_allowed(self):
        from qwed_tax.jurisdictions.india.guards.setoff_guard import (
            InterHeadAdjustmentGuard, TaxHead,
        )
        guard = InterHeadAdjustmentGuard()
        raw = guard.verify_setoff(TaxHead.HOUSE_PROPERTY, TaxHead.SALARY)
        diag = InterHeadAdjustmentGuard.to_diagnostic(raw)
        assert diag.status is TaxDiagnosticStatus.VERIFIED
        assert diag.proof_ref is not None
        assert diag.developer_fields["constraint_id"] == "INTERHEAD_SETOFF_71"

    def test_blocked_vda_lapses(self):
        from qwed_tax.jurisdictions.india.guards.setoff_guard import (
            InterHeadAdjustmentGuard, TaxHead,
        )
        guard = InterHeadAdjustmentGuard()
        raw = guard.verify_setoff(TaxHead.VDA, TaxHead.SALARY)
        diag = InterHeadAdjustmentGuard.to_diagnostic(raw)
        assert diag.status is TaxDiagnosticStatus.BLOCKED
        assert diag.proof_ref is None

    def test_blocked_speculative_against_salary(self):
        from qwed_tax.jurisdictions.india.guards.setoff_guard import (
            InterHeadAdjustmentGuard, TaxHead,
        )
        guard = InterHeadAdjustmentGuard()
        raw = guard.verify_setoff(TaxHead.BUSINESS_SPECULATIVE, TaxHead.SALARY)
        diag = InterHeadAdjustmentGuard.to_diagnostic(raw)
        assert diag.status is TaxDiagnosticStatus.BLOCKED
        assert diag.developer_fields["constraint_id"] == "SPECULATIVE_SETOFF_73"

    def test_unverifiable_unknown_head(self):
        from qwed_tax.jurisdictions.india.guards.setoff_guard import TaxHead
        # Simulate an unknown head not in matrix or allowlist
        # TaxHead doesn't have an "unknown" member, so we test via the
        # to_diagnostic path directly with a crafted result
        from qwed_tax.jurisdictions.india.guards.setoff_guard import InterHeadAdjustmentGuard
        from qwed_tax.audit import build_trace, INTERHEAD_SETOFF_71
        raw = {
            "verified": False,
            "message": "Loss head UNKNOWN is not in the configured prohibition matrix.",
            "audit_trace": build_trace(INTERHEAD_SETOFF_71, "UNKNOWN_HEAD", {"loss_head": "UNKNOWN"}),
        }
        diag = InterHeadAdjustmentGuard.to_diagnostic(raw)
        assert diag.status is TaxDiagnosticStatus.UNVERIFIABLE
        assert diag.proof_ref is None

    def test_verified_without_audit_trace_raises(self):
        from qwed_tax.jurisdictions.india.guards.setoff_guard import InterHeadAdjustmentGuard
        with pytest.raises(ValueError, match="audit_trace"):
            InterHeadAdjustmentGuard.to_diagnostic({"verified": True})


class TestCryptoTaxGuardDiagnostic:
    def test_verified_no_vda_loss(self):
        from qwed_tax.jurisdictions.india.guards.crypto_guard import CryptoTaxGuard
        guard = CryptoTaxGuard()
        raw = guard.verify_set_off({"EQUITY": Decimal("-200")})
        diag = CryptoTaxGuard.to_diagnostic(raw)
        assert diag.status is TaxDiagnosticStatus.VERIFIED
        assert diag.proof_ref is not None
        assert diag.developer_fields["constraint_id"] == "VDA_115BBH"

    def test_blocked_vda_loss_setoff(self):
        from qwed_tax.jurisdictions.india.guards.crypto_guard import CryptoTaxGuard
        guard = CryptoTaxGuard()
        raw = guard.verify_set_off({"VDA": Decimal("-5000")})
        diag = CryptoTaxGuard.to_diagnostic(raw)
        assert diag.status is TaxDiagnosticStatus.BLOCKED
        assert diag.proof_ref is None
        assert diag.developer_fields["constraint_id"] == "VDA_SETOFF_PROHIBITION"

    def test_unverifiable_gain_side_not_implemented(self):
        from qwed_tax.jurisdictions.india.guards.crypto_guard import CryptoTaxGuard
        guard = CryptoTaxGuard()
        raw = guard.verify_set_off({"VDA": Decimal("-5000")}, gains={"BUSINESS": Decimal("10000")})
        diag = CryptoTaxGuard.to_diagnostic(raw)
        assert diag.status is TaxDiagnosticStatus.UNVERIFIABLE
        assert diag.proof_ref is None

    def test_verified_flat_tax_correct(self):
        from qwed_tax.jurisdictions.india.guards.crypto_guard import CryptoTaxGuard
        guard = CryptoTaxGuard()
        raw = guard.verify_flat_tax_rate(Decimal("100000"), Decimal("30000"))
        diag = CryptoTaxGuard.to_diagnostic(raw)
        assert diag.status is TaxDiagnosticStatus.VERIFIED
        assert diag.proof_ref is not None

    def test_blocked_flat_tax_mismatch(self):
        from qwed_tax.jurisdictions.india.guards.crypto_guard import CryptoTaxGuard
        guard = CryptoTaxGuard()
        raw = guard.verify_flat_tax_rate(Decimal("100000"), Decimal("20000"))
        diag = CryptoTaxGuard.to_diagnostic(raw)
        assert diag.status is TaxDiagnosticStatus.BLOCKED
        assert "115BBH" in diag.developer_fields["error"]

    def test_blocked_negative_income(self):
        from qwed_tax.jurisdictions.india.guards.crypto_guard import CryptoTaxGuard
        guard = CryptoTaxGuard()
        raw = guard.verify_flat_tax_rate(Decimal("-5000"), Decimal("0"))
        diag = CryptoTaxGuard.to_diagnostic(raw)
        assert diag.status is TaxDiagnosticStatus.BLOCKED
        assert "negative" in diag.developer_fields["error"].lower()


class TestValuationGuardDiagnostic:
    def test_verified_cap_method(self):
        from qwed_tax.guards.valuation_guard import ValuationGuard
        guard = ValuationGuard()
        raw = guard.verify_conversion("100000", "5.00", "0.20", "10.00")
        diag = ValuationGuard.to_diagnostic(raw)
        assert diag.status is TaxDiagnosticStatus.VERIFIED
        assert diag.proof_ref is not None
        assert diag.developer_fields["constraint_id"] == "SAFE_CONVERSION"
        assert diag.developer_fields["method"] == "CAP"

    def test_blocked_invalid_input(self):
        from qwed_tax.guards.valuation_guard import ValuationGuard
        guard = ValuationGuard()
        raw = guard.verify_conversion("abc", "5.00", "0.20", "10.00")
        diag = ValuationGuard.to_diagnostic(raw)
        assert diag.status is TaxDiagnosticStatus.BLOCKED
        assert diag.proof_ref is None
        assert "Invalid" in diag.developer_fields["error"]

    def test_blocked_discount_out_of_range(self):
        from qwed_tax.guards.valuation_guard import ValuationGuard
        guard = ValuationGuard()
        raw = guard.verify_conversion("100000", "5.00", "1.5", "10.00")
        diag = ValuationGuard.to_diagnostic(raw)
        assert diag.status is TaxDiagnosticStatus.BLOCKED
        assert "Discount" in diag.developer_fields["error"]

    def test_verified_without_audit_trace_raises(self):
        from qwed_tax.guards.valuation_guard import ValuationGuard
        with pytest.raises(ValueError, match="audit_trace"):
            ValuationGuard.to_diagnostic({"verified": True})


class TestRemittanceGuardDiagnostic:
    def test_verified_within_limit(self):
        from qwed_tax.guards.remittance_guard import RemittanceGuard
        guard = RemittanceGuard()
        raw = guard.verify_lrs_limit("50000", "EDUCATION", "100000")
        diag = RemittanceGuard.to_diagnostic(raw)
        assert diag.status is TaxDiagnosticStatus.VERIFIED
        assert diag.proof_ref is not None
        assert diag.developer_fields["constraint_id"] == "LRS_LIMIT"

    def test_blocked_limit_exceeded(self):
        from qwed_tax.guards.remittance_guard import RemittanceGuard
        guard = RemittanceGuard()
        raw = guard.verify_lrs_limit("200000", "INVESTMENT", "100000")
        diag = RemittanceGuard.to_diagnostic(raw)
        assert diag.status is TaxDiagnosticStatus.BLOCKED
        assert diag.proof_ref is None
        assert "LRS limit" in diag.developer_fields["error"]

    def test_blocked_prohibited(self):
        from qwed_tax.guards.remittance_guard import RemittanceGuard
        guard = RemittanceGuard()
        raw = guard.verify_lrs_limit("5000", "GAMBLING", "0")
        diag = RemittanceGuard.to_diagnostic(raw)
        assert diag.status is TaxDiagnosticStatus.BLOCKED
        assert diag.developer_fields["constraint_id"] == "FEMA_SCHEDULE_I"
        assert "prohibited" in diag.developer_fields["error"].lower()

    def test_blocked_negative_amount(self):
        from qwed_tax.guards.remittance_guard import RemittanceGuard
        guard = RemittanceGuard()
        raw = guard.verify_lrs_limit("-5000", "EDUCATION", "0")
        diag = RemittanceGuard.to_diagnostic(raw)
        assert diag.status is TaxDiagnosticStatus.BLOCKED
        assert "non-negative" in diag.developer_fields["error"]

    def test_verified_without_audit_trace_raises(self):
        from qwed_tax.guards.remittance_guard import RemittanceGuard
        with pytest.raises(ValueError, match="audit_trace"):
            RemittanceGuard.to_diagnostic({"verified": True})


class TestPoEMGuardDiagnostic:
    def test_verified_non_resident_aboi(self):
        from qwed_tax.guards.poem_guard import PoEMGuard
        guard = PoEMGuard()
        raw = guard.determine_residency(
            company_name="GlobalCorp",
            is_foreign_incorp=True,
            turnover_total="10000000",
            turnover_outside_india="8000000",
            assets_total="5000000",
            assets_outside_india="4000000",
            employees_total=100,
            employees_outside_india=80,
            payroll_total="1000000",
            payroll_outside_india="800000",
            key_management_location="USA",
        )
        diag = PoEMGuard.to_diagnostic(raw)
        assert diag.status is TaxDiagnosticStatus.VERIFIED
        assert diag.proof_ref is not None
        assert diag.developer_fields["constraint_id"] == "POEM_CBDT_6_2017"
        assert diag.developer_fields["residency"] == "NON_RESIDENT"

    def test_verified_resident_domestic(self):
        from qwed_tax.guards.poem_guard import PoEMGuard
        guard = PoEMGuard()
        raw = guard.determine_residency(
            company_name="IndiaCorp",
            is_foreign_incorp=False,
            turnover_total="10000000",
            turnover_outside_india="0",
            assets_total="5000000",
            assets_outside_india="0",
            employees_total=100,
            employees_outside_india=0,
            payroll_total="1000000",
            payroll_outside_india="0",
            key_management_location="India",
        )
        diag = PoEMGuard.to_diagnostic(raw)
        assert diag.status is TaxDiagnosticStatus.VERIFIED
        assert diag.developer_fields["constraint_id"] == "POEM_SECTION_6_3"
        assert diag.developer_fields["residency"] == "RESIDENT"

    def test_unverifiable_invalid_input(self):
        from qwed_tax.guards.poem_guard import PoEMGuard
        guard = PoEMGuard()
        raw = guard.determine_residency(
            company_name="Corp",
            is_foreign_incorp=True,
            turnover_total="abc",
            turnover_outside_india="0",
            assets_total="5000000",
            assets_outside_india="0",
            employees_total=100,
            employees_outside_india=0,
            payroll_total="1000000",
            payroll_outside_india="0",
            key_management_location="India",
        )
        diag = PoEMGuard.to_diagnostic(raw)
        assert diag.status is TaxDiagnosticStatus.BLOCKED
        assert diag.proof_ref is None

    def test_verified_without_audit_trace_raises(self):
        from qwed_tax.guards.poem_guard import PoEMGuard
        with pytest.raises(ValueError, match="audit_trace"):
            PoEMGuard.to_diagnostic({"verified": True})


class TestWithholdingGuardDiagnostic:
    def test_verified_valid_exempt(self):
        from qwed_tax.jurisdictions.us.withholding_guard import WithholdingGuard, W4Form
        guard = WithholdingGuard()
        form = W4Form(
            employee_id="E001",
            claim_exempt=True,
            tax_liability_last_year=Decimal("0"),
            expect_refund_this_year=True,
        )
        raw = guard.verify_exempt_status(form)
        diag = WithholdingGuard.to_diagnostic(raw)
        assert diag.status is TaxDiagnosticStatus.VERIFIED
        assert diag.proof_ref is not None
        assert diag.developer_fields["constraint_id"] == "W4_EXEMPT_PUB505"

    def test_blocked_violation(self):
        from qwed_tax.jurisdictions.us.withholding_guard import WithholdingGuard, W4Form
        guard = WithholdingGuard()
        form = W4Form(
            employee_id="E001",
            claim_exempt=True,
            tax_liability_last_year=Decimal("5000"),
            expect_refund_this_year=True,
        )
        raw = guard.verify_exempt_status(form)
        diag = WithholdingGuard.to_diagnostic(raw)
        assert diag.status is TaxDiagnosticStatus.BLOCKED
        assert diag.proof_ref is None
        assert "VIOLATION" in diag.developer_fields["error"]

    def test_verified_without_audit_trace_raises(self):
        from qwed_tax.jurisdictions.us.withholding_guard import WithholdingGuard
        with pytest.raises(ValueError, match="audit_trace"):
            WithholdingGuard.to_diagnostic({"verified": True})


class TestAllGuardsSerialization:
    """Verify to_dict/from_dict round-trip works for all migrated guards."""

    def test_capital_gains_roundtrip(self):
        from qwed_tax.guards.capital_gains_guard import CapitalGainsGuard
        guard = CapitalGainsGuard()
        raw = guard.verify_tax_rate("equity", "LTCG", "12.5%")
        diag = CapitalGainsGuard.to_diagnostic(raw)
        restored = TaxDiagnosticResult.from_dict(diag.to_dict())
        assert restored.status == diag.status
        assert restored.agent_message == diag.agent_message
        assert restored.proof_ref == diag.proof_ref

    def test_crypto_roundtrip(self):
        from qwed_tax.jurisdictions.india.guards.crypto_guard import CryptoTaxGuard
        guard = CryptoTaxGuard()
        raw = guard.verify_flat_tax_rate(Decimal("100000"), Decimal("30000"))
        diag = CryptoTaxGuard.to_diagnostic(raw)
        restored = TaxDiagnosticResult.from_dict(diag.to_dict())
        assert restored.status == diag.status
        assert restored.proof_ref == diag.proof_ref

    def test_withholding_roundtrip(self):
        from qwed_tax.jurisdictions.us.withholding_guard import WithholdingGuard, W4Form
        guard = WithholdingGuard()
        form = W4Form(
            employee_id="E001",
            claim_exempt=True,
            tax_liability_last_year=Decimal("0"),
            expect_refund_this_year=True,
        )
        raw = guard.verify_exempt_status(form)
        diag = WithholdingGuard.to_diagnostic(raw)
        restored = TaxDiagnosticResult.from_dict(diag.to_dict())
        assert restored.status == diag.status
        assert restored.proof_ref == diag.proof_ref

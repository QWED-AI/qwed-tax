"""Tests for input strictness fixes: #20 (tolerance), #21 (edge-case), #22 (extra fields)."""

from decimal import Decimal

import pytest
from pydantic import ValidationError

from qwed_tax.guards.remittance_guard import RemittanceGuard
from qwed_tax.guards.valuation_guard import ValuationGuard
from qwed_tax.jurisdictions.india.guards.crypto_guard import CryptoTaxGuard
from qwed_tax.models import (
    Address,
    ContractorPayment,
    DeductionEntry,
    DeductionType,
    PayrollEntry,
    State,
    TaxEntry,
    VerificationResult,
    WorkArrangement,
    WorkerClassificationParams,
)


class TestIssue20CryptoTolerance:
    """CryptoTaxGuard must use exact paise-level comparison, not tolerance."""

    def setup_method(self):
        self.guard = CryptoTaxGuard()

    def test_exact_match_passes(self):
        res = self.guard.verify_flat_tax_rate(Decimal("10000"), Decimal("3000.00"))
        assert res.verified is True

    def test_tolerance_no_longer_accepted(self):
        res = self.guard.verify_flat_tax_rate(Decimal("10000"), Decimal("2999.91"))
        assert res.verified is False

    def test_one_paise_off_blocked(self):
        res = self.guard.verify_flat_tax_rate(Decimal("10000"), Decimal("3000.01"))
        assert res.verified is False

    def test_paise_rounding_exact(self):
        res = self.guard.verify_flat_tax_rate(Decimal("3333"), Decimal("999.90"))
        assert res.verified is True

    def test_paise_rounding_rejects_wrong(self):
        res = self.guard.verify_flat_tax_rate(Decimal("3333"), Decimal("999.91"))
        assert res.verified is False


class TestIssue21ValuationEdgeCases:
    """ValuationGuard must reject edge-case inputs."""

    def setup_method(self):
        self.guard = ValuationGuard()

    def test_discount_above_1_blocked(self):
        res = self.guard.verify_conversion("100000", "100", "2", "100")
        assert res["verified"] is False
        assert "Discount must be between 0 and 1" in res["error"]

    def test_negative_discount_blocked(self):
        res = self.guard.verify_conversion("100000", "100", "-0.5", "100")
        assert res["verified"] is False

    def test_zero_cap_blocked(self):
        res = self.guard.verify_conversion("100000", "0", "0.2", "100")
        assert res["verified"] is False
        assert "must be positive" in res["error"]

    def test_zero_next_round_price_blocked(self):
        res = self.guard.verify_conversion("100000", "100", "0.2", "0")
        assert res["verified"] is False

    def test_zero_investment_blocked(self):
        res = self.guard.verify_conversion("0", "100", "0.2", "100")
        assert res["verified"] is False

    def test_negative_investment_blocked(self):
        res = self.guard.verify_conversion("-1000", "100", "0.2", "100")
        assert res["verified"] is False

    def test_valid_conversion_passes(self):
        res = self.guard.verify_conversion("100000", "80", "0.2", "100")
        assert res["verified"] is True
        assert res["method"] == "CAP"

    def test_valid_discount_path_passes(self):
        res = self.guard.verify_conversion("100000", "100", "0.2", "100")
        assert res["verified"] is True
        assert res["method"] == "DISCOUNT"


class TestIssue21RemittanceNegative:
    """RemittanceGuard must reject negative amounts."""

    def setup_method(self):
        self.guard = RemittanceGuard()

    def test_negative_remittance_blocked(self):
        res = self.guard.verify_lrs_limit(-500000, "education", 200000)
        assert res["verified"] is False
        assert "non-negative" in res["error"]

    def test_negative_usage_blocked(self):
        res = self.guard.verify_lrs_limit(50000, "education", -100)
        assert res["verified"] is False
        assert "non-negative" in res["error"]

    def test_zero_remittance_passes(self):
        res = self.guard.verify_lrs_limit(0, "education", 0)
        assert res["verified"] is True

    def test_valid_remittance_passes(self):
        res = self.guard.verify_lrs_limit(50000, "education", 100000)
        assert res["verified"] is True


class TestIssue22ExtraFieldsForbid:
    """All Pydantic models must reject unexpected fields."""

    def _valid_payroll(self, **extra):
        data = {
            "employee_id": "E001",
            "gross_pay": "5000.00",
            "taxes": [{"name": "Fed", "amount": "800.00"}],
            "deductions": [{"name": "401k", "amount": "500.00", "type": "PRE_TAX"}],
            "net_pay_claimed": "3390.00",
        }
        data.update(extra)
        return data

    def test_payroll_entry_rejects_extra_field(self):
        with pytest.raises(ValidationError):
            PayrollEntry.model_validate(self._valid_payroll(override_tax_mode="disable"))

    def test_address_rejects_extra_field(self):
        with pytest.raises(ValidationError):
            Address.model_validate({
                "street": "1 Main St",
                "city": "NYC",
                "state": "NY",
                "zip_code": "10001",
                "country": "US",
            })

    def test_work_arrangement_rejects_extra_field(self):
        addr = {"street": "1 Main", "city": "NYC", "state": "NY", "zip_code": "10001"}
        with pytest.raises(ValidationError):
            WorkArrangement.model_validate({
                "employee_id": "E1",
                "residence_address": addr,
                "work_address": addr,
                "override": True,
            })

    def test_worker_classification_rejects_extra_field(self):
        with pytest.raises(ValidationError):
            WorkerClassificationParams.model_validate({
                "worker_id": "W1",
                "freedom_from_control": True,
                "work_outside_usual_business": False,
                "customarily_engaged_independently": True,
                "state": "NY",
                "override": True,
            })

    def test_contractor_payment_rejects_extra_field(self):
        with pytest.raises(ValidationError):
            ContractorPayment.model_validate({
                "contractor_id": "C1",
                "payment_type": "NEC",
                "amount": "1000.00",
                "calendar_year": 2024,
                "bonus": "500",
            })

    def test_tax_entry_rejects_extra_field(self):
        with pytest.raises(ValidationError):
            TaxEntry.model_validate({"name": "Fed", "amount": "800.00", "extra": True})

    def test_deduction_entry_rejects_extra_field(self):
        with pytest.raises(ValidationError):
            DeductionEntry.model_validate({
                "name": "401k",
                "amount": "500.00",
                "type": "PRE_TAX",
                "extra": True,
            })

    def test_verification_result_rejects_extra_field(self):
        with pytest.raises(ValidationError):
            VerificationResult.model_validate({
                "verified": True,
                "recalculated_net_pay": "5000",
                "discrepancy": "0",
                "message": "OK",
                "extra_field": True,
            })

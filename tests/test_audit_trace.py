"""Tests for structured statutory audit-trace on guard verdicts."""

import pytest

from qwed_tax.audit import build_trace, ITC_BLOCKED_17_5, JURISDICTION_INDIA
from qwed_tax.guards.indirect_tax_guard import InputCreditGuard
from qwed_tax.guards.tds_guard import TDSGuard


class TestBuildTrace:
    def test_trace_shape(self):
        trace = build_trace(ITC_BLOCKED_17_5, "BLOCKED", {"expense_category": "CATERING"})
        assert trace["rule_id"] == "ITC_BLOCKED_17_5"
        assert trace["statute"] == "CGST Act, Section 17(5)"
        assert trace["jurisdiction"] == JURISDICTION_INDIA
        assert trace["outcome"] == "BLOCKED"
        assert trace["inputs"] == {"expense_category": "CATERING"}

    def test_trace_inputs_default_empty(self):
        trace = build_trace(ITC_BLOCKED_17_5, "BLOCKED")
        assert trace["inputs"] == {}

    def test_trace_inputs_are_copied(self):
        src = {"a": 1}
        trace = build_trace(ITC_BLOCKED_17_5, "BLOCKED", src)
        src["a"] = 2
        assert trace["inputs"]["a"] == 1  # snapshot, not a live reference

    def test_trace_inputs_deep_copied(self):
        src = {"legs": ["cgst"]}
        trace = build_trace(ITC_BLOCKED_17_5, "BLOCKED", src)
        src["legs"].append("sgst")
        assert trace["inputs"]["legs"] == ["cgst"]  # nested mutation must not leak

    def test_rule_ref_is_immutable(self):
        import dataclasses

        with pytest.raises(dataclasses.FrozenInstanceError):
            ITC_BLOCKED_17_5.rule_id = "tampered"


class TestITCAuditTrace:
    def setup_method(self):
        self.guard = InputCreditGuard()

    def test_blocked_category_emits_17_5_trace(self):
        res = self.guard.verify_itc_eligibility("food and beverage", 5000, 900)
        assert res["verified"] is False
        assert res["audit_trace"]["rule_id"] == "ITC_BLOCKED_17_5"
        assert res["audit_trace"]["outcome"] == "BLOCKED"
        # Backward compatibility: legacy keys unchanged.
        assert res["eligible_itc"] == "0"
        assert "reason" in res

    def test_personal_consumption_emits_trace(self):
        res = self.guard.verify_itc_eligibility("personal expense", 500, 90)
        assert res["audit_trace"]["rule_id"] == "ITC_PERSONAL_CONSUMPTION"
        # Personal consumption is blocked under 17(5)(g), not the apportionment
        # rule 17(1).
        assert res["audit_trace"]["statute"] == "CGST Act, Section 17(5)(g)"

    def test_eligible_expense_emits_trace(self):
        res = self.guard.verify_itc_eligibility("office supplies", 1000, 180)
        assert res["verified"] is True
        assert res["audit_trace"]["rule_id"] == "ITC_ELIGIBLE"
        assert res["audit_trace"]["outcome"] == "ALLOWED"

    def test_gift_below_threshold_emits_trace(self):
        res = self.guard.verify_itc_eligibility("gift to employee", 30000, 5400)
        assert res["audit_trace"]["rule_id"] == "ITC_GIFT_THRESHOLD"
        assert res["audit_trace"]["outcome"] == "ALLOWED"

    def test_gift_above_threshold_emits_specific_17_5_h_trace(self):
        # Over-threshold gift must cite the specific 17(5)(h), not the general 17(5).
        res = self.guard.verify_itc_eligibility("gift to employee", 60000, 10800)
        assert res["verified"] is False
        assert res["audit_trace"]["rule_id"] == "ITC_GIFT_THRESHOLD"
        assert res["audit_trace"]["statute"] == "CGST Act, Section 17(5)(h)"
        assert res["audit_trace"]["outcome"] == "BLOCKED"


class TestTDSAuditTrace:
    def setup_method(self):
        self.guard = TDSGuard()

    def test_deduction_required_emits_section_trace(self):
        # Professional fees -> Sec 194J, threshold crossed.
        res = self.guard.calculate_deduction("PROFESSIONAL_FEES", 50000, 0)
        assert res["audit_trace"]["rule_id"] == "TDS_194J"
        assert res["audit_trace"]["statute"] == "Income Tax Act, Section 194J"
        assert res["audit_trace"]["outcome"] == "DEDUCTION_REQUIRED"
        # Legacy keys preserved.
        assert res["deduction"] == "5000.00"

    def test_below_threshold_emits_trace(self):
        res = self.guard.calculate_deduction("PROFESSIONAL_FEES", 1000, 0)
        assert res["audit_trace"]["outcome"] == "BELOW_THRESHOLD"
        assert res["audit_trace"]["rule_id"] == "TDS_194J"

    def test_contractor_firm_maps_to_194c(self):
        res = self.guard.calculate_deduction("CONTRACTOR_FIRM", 50000, 0)
        assert res["audit_trace"]["rule_id"] == "TDS_194C"

    def test_unknown_category_has_no_trace(self):
        # No statutory rule applies, so no trace is emitted (legacy behavior).
        res = self.guard.calculate_deduction("UNKNOWN_SERVICE", 50000, 0)
        assert "audit_trace" not in res
        assert res["verified"] is True

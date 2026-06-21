"""Tests for TaxDiagnosticResult 3-layer model (#39)."""

from dataclasses import FrozenInstanceError

import pytest

from qwed_tax.audit import TDS_194J, build_trace, trace_proof_ref
from qwed_tax.diagnostics import (
    TaxAdvisoryCheck,
    TaxDiagnosticResult,
    TaxDiagnosticStatus,
    compute_proof_ref,
)
from qwed_tax.guards.indirect_tax_guard import InputCreditGuard
from qwed_tax.guards.tds_guard import TDSGuard
from qwed_tax.jurisdictions.india.guards.gst_guard import EntityType, GSTGuard, ServiceType


# ---------------------------------------------------------------------------
# TaxDiagnosticResult model tests
# ---------------------------------------------------------------------------

class TestTaxDiagnosticResultModel:
    """Core model invariants — 3 layers, frozen, status/proof_ref contract."""

    def test_verified_requires_proof_ref(self):
        with pytest.raises(ValueError, match="VERIFIED status requires proof_ref"):
            TaxDiagnosticResult(
                status=TaxDiagnosticStatus.VERIFIED,
                agent_message="ok",
                developer_fields={},
                proof_ref=None,
            )

    def test_non_verified_rejects_proof_ref(self):
        with pytest.raises(ValueError, match="UNVERIFIABLE status requires proof_ref is None"):
            TaxDiagnosticResult(
                status=TaxDiagnosticStatus.UNVERIFIABLE,
                agent_message="cannot verify",
                developer_fields={},
                proof_ref="sha256:abc",
            )

    def test_blocked_rejects_proof_ref(self):
        with pytest.raises(ValueError, match="BLOCKED status requires proof_ref is None"):
            TaxDiagnosticResult(
                status=TaxDiagnosticStatus.BLOCKED,
                agent_message="blocked",
                developer_fields={},
                proof_ref="sha256:abc",
            )

    def test_empty_agent_message_rejected(self):
        with pytest.raises(ValueError, match="agent_message must be a non-empty string"):
            TaxDiagnosticResult(
                status=TaxDiagnosticStatus.BLOCKED,
                agent_message="",
            )

    def test_frozen_dataclass(self):
        result = TaxDiagnosticResult.blocked("blocked")
        with pytest.raises(FrozenInstanceError):
            result.agent_message = "mutated"

    def test_verified_factory_produces_proof_ref(self):
        result = TaxDiagnosticResult.verified(
            agent_message="verified",
            developer_fields={"constraint_id": "TEST_RULE"},
            evidence={"rule_id": "TEST_RULE", "outcome": "PASS"},
        )
        assert result.status is TaxDiagnosticStatus.VERIFIED
        assert result.proof_ref is not None
        assert result.proof_ref.startswith("sha256:")

    def test_unverifiable_factory(self):
        result = TaxDiagnosticResult.unverifiable(
            "cannot verify",
            {"constraint_id": "TEST"},
        )
        assert result.status is TaxDiagnosticStatus.UNVERIFIABLE
        assert result.proof_ref is None
        assert result.is_fail_closed is True

    def test_blocked_factory(self):
        result = TaxDiagnosticResult.blocked(
            "blocked",
            {"constraint_id": "TEST"},
        )
        assert result.status is TaxDiagnosticStatus.BLOCKED
        assert result.proof_ref is None
        assert result.is_fail_closed is True

    def test_is_verified_property(self):
        verified = TaxDiagnosticResult.verified("ok", {}, {"x": 1})
        assert verified.is_verified is True
        assert verified.is_authoritative is True

        unverified = TaxDiagnosticResult.unverifiable("no")
        assert unverified.is_verified is False
        assert unverified.is_authoritative is False

    def test_to_dict_and_from_dict_roundtrip(self):
        result = TaxDiagnosticResult.verified(
            agent_message="verified",
            developer_fields={"constraint_id": "TDS_194J", "deduction": "3000"},
            evidence={"rule_id": "TDS_194J"},
        )
        d = result.to_dict()
        assert d["status"] == "VERIFIED"
        assert d["proof_ref"].startswith("sha256:")
        assert d["is_authoritative"] is True

        restored = TaxDiagnosticResult.from_dict(d)
        assert restored.status is TaxDiagnosticStatus.VERIFIED
        assert restored.agent_message == "verified"
        assert restored.proof_ref == result.proof_ref

    def test_from_dict_rejects_invalid_status(self):
        with pytest.raises(ValueError, match="invalid status"):
            TaxDiagnosticResult.from_dict({
                "status": "HEURISTIC",
                "agent_message": "test",
            })

    def test_from_dict_rejects_empty_agent_message(self):
        with pytest.raises(ValueError, match="agent_message"):
            TaxDiagnosticResult.from_dict({
                "status": "BLOCKED",
                "agent_message": "",
            })

    def test_constraint_id_property(self):
        result = TaxDiagnosticResult.blocked("blocked", {"constraint_id": "ITC_BLOCKED_17_5"})
        assert result.constraint_id == "ITC_BLOCKED_17_5"

    def test_audit_trace_property(self):
        trace = build_trace(TDS_194J, "DEDUCTION_REQUIRED", {"amount": "50000"})
        result = TaxDiagnosticResult.verified(
            "verified",
            {"constraint_id": "TDS_194J", "audit_trace": trace},
            trace,
        )
        assert result.audit_trace == trace


# ---------------------------------------------------------------------------
# TaxAdvisoryCheck tests
# ---------------------------------------------------------------------------

class TestTaxAdvisoryCheck:
    def test_advisory_only_must_be_true(self):
        with pytest.raises(ValueError, match="advisory_only must be True"):
            TaxAdvisoryCheck(name="heuristic", advisory_only=False)

    def test_to_dict_and_from_dict_roundtrip(self):
        check = TaxAdvisoryCheck(name="heuristic_check", constraint_id="ADVISORY_1")
        d = check.to_dict()
        assert d["advisory_only"] is True
        restored = TaxAdvisoryCheck.from_dict(d)
        assert restored.name == "heuristic_check"
        assert restored.advisory_only is True

    def test_advisory_checks_in_result(self):
        check = TaxAdvisoryCheck(name="heuristic", constraint_id="ADVISORY_1")
        result = TaxDiagnosticResult.unverifiable(
            "cannot verify",
            {"advisory_checks": [check]},
        )
        checks = result.advisory_checks
        assert len(checks) == 1
        assert checks[0].name == "heuristic"


# ---------------------------------------------------------------------------
# compute_proof_ref tests
# ---------------------------------------------------------------------------

class TestComputeProofRef:
    def test_deterministic_hash(self):
        evidence = {"rule_id": "TDS_194J", "outcome": "PASS"}
        ref1 = compute_proof_ref(evidence)
        ref2 = compute_proof_ref(evidence)
        assert ref1 == ref2
        assert ref1.startswith("sha256:")

    def test_different_evidence_different_hash(self):
        ref1 = compute_proof_ref({"rule_id": "TDS_194J"})
        ref2 = compute_proof_ref({"rule_id": "TDS_194C"})
        assert ref1 != ref2

    def test_non_serializable_raises(self):
        with pytest.raises(ValueError, match="JSON-serializable"):
            compute_proof_ref({"non_serializable": object()})


# ---------------------------------------------------------------------------
# trace_proof_ref tests
# ---------------------------------------------------------------------------

class TestTraceProofRef:
    def test_trace_proof_ref_matches_compute_proof_ref(self):
        trace = build_trace(TDS_194J, "DEDUCTION_REQUIRED", {"amount": "50000"})
        ref1 = trace_proof_ref(trace)
        ref2 = compute_proof_ref(trace)
        assert ref1 == ref2

    def test_different_traces_different_hash(self):
        trace1 = build_trace(TDS_194J, "DEDUCTION_REQUIRED", {"amount": "50000"})
        trace2 = build_trace(TDS_194J, "BELOW_THRESHOLD", {"amount": "50000"})
        assert trace_proof_ref(trace1) != trace_proof_ref(trace2)


# ---------------------------------------------------------------------------
# Guard migration tests — TDS, ITC, GST-RCM
# ---------------------------------------------------------------------------

class TestTDSGuardMigration:
    """TDSGuard.to_diagnostic() converts legacy dict to TaxDiagnosticResult."""

    def setup_method(self):
        self.guard = TDSGuard()

    def test_deduction_required_to_diagnostic(self):
        result = self.guard.calculate_deduction("PROFESSIONAL_FEES", "50000", "0")
        diag = TDSGuard.to_diagnostic(result)
        assert diag.status is TaxDiagnosticStatus.VERIFIED
        assert diag.proof_ref is not None
        assert diag.constraint_id == "TDS_194J"
        assert diag.developer_fields["deduction"] is not None

    def test_below_threshold_to_diagnostic(self):
        result = self.guard.calculate_deduction("PROFESSIONAL_FEES", "1000", "0")
        diag = TDSGuard.to_diagnostic(result)
        assert diag.status is TaxDiagnosticStatus.VERIFIED
        assert diag.proof_ref is not None
        assert diag.constraint_id == "TDS_194J"

    def test_unknown_service_to_diagnostic(self):
        result = self.guard.calculate_deduction("UNKNOWN_TYPE", "50000", "0")
        diag = TDSGuard.to_diagnostic(result)
        assert diag.status is TaxDiagnosticStatus.BLOCKED
        assert diag.proof_ref is None
        assert diag.constraint_id == "TDS_UNKNOWN"


class TestITCGuardMigration:
    """InputCreditGuard.to_diagnostic() converts legacy dict to TaxDiagnosticResult."""

    def setup_method(self):
        self.guard = InputCreditGuard()

    def test_eligible_to_diagnostic(self):
        result = self.guard.verify_itc_eligibility("OFFICE_SUPPLIES", "1000", "180")
        diag = InputCreditGuard.to_diagnostic(result)
        assert diag.status is TaxDiagnosticStatus.VERIFIED
        assert diag.proof_ref is not None
        assert diag.constraint_id == "ITC_ELIGIBLE"

    def test_blocked_to_diagnostic(self):
        result = self.guard.verify_itc_eligibility("FOOD_AND_BEVERAGE", "1000", "180")
        diag = InputCreditGuard.to_diagnostic(result)
        assert diag.status is TaxDiagnosticStatus.BLOCKED
        assert diag.proof_ref is None
        assert diag.constraint_id == "ITC_BLOCKED_17_5"

    def test_gift_threshold_to_diagnostic(self):
        result = self.guard.verify_itc_eligibility("GIFT_TO_EMPLOYEE", "40000", "7200")
        diag = InputCreditGuard.to_diagnostic(result)
        assert diag.status is TaxDiagnosticStatus.VERIFIED
        assert diag.constraint_id == "ITC_GIFT_THRESHOLD"


class TestGSTRCMGuardMigration:
    """GSTGuard.to_diagnostic() converts legacy dict to TaxDiagnosticResult."""

    def setup_method(self):
        self.guard = GSTGuard()

    def test_verification_mode_match_to_diagnostic(self):
        result = self.guard.verify_rcm_applicability(
            ServiceType.GTA, EntityType.INDIVIDUAL, EntityType.BODY_CORPORATE,
            claimed_is_rcm=True,
        )
        diag = GSTGuard.to_diagnostic(result)
        assert diag.status is TaxDiagnosticStatus.VERIFIED
        assert diag.proof_ref is not None
        assert diag.constraint_id == "RCM_GTA"

    def test_verification_mode_mismatch_to_diagnostic(self):
        result = self.guard.verify_rcm_applicability(
            ServiceType.GTA, EntityType.INDIVIDUAL, EntityType.BODY_CORPORATE,
            claimed_is_rcm=False,
        )
        diag = GSTGuard.to_diagnostic(result)
        assert diag.status is TaxDiagnosticStatus.BLOCKED
        assert diag.proof_ref is None

    def test_computation_mode_to_diagnostic(self):
        result = self.guard.verify_rcm_applicability(
            ServiceType.GTA, EntityType.INDIVIDUAL, EntityType.BODY_CORPORATE,
        )
        diag = GSTGuard.to_diagnostic(result)
        assert diag.status is TaxDiagnosticStatus.UNVERIFIABLE
        assert diag.proof_ref is None
        assert diag.developer_fields.get("constraint_id") == "RCM_GTA"

    def test_unknown_service_to_diagnostic(self):
        result = self.guard.verify_rcm_applicability(
            "MYSTERY", "INDIVIDUAL", "BODY_CORPORATE",
        )
        diag = GSTGuard.to_diagnostic(result)
        assert diag.status is TaxDiagnosticStatus.BLOCKED
        assert diag.proof_ref is None

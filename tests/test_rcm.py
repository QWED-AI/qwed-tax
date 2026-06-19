"""Tests for GST Reverse Charge Mechanism (RCM) applicability."""

from qwed_tax.jurisdictions.india.guards.gst_guard import (
    EntityType,
    GSTGuard,
    ServiceType,
)


class TestRCMApplicability:
    def setup_method(self):
        self.guard = GSTGuard()

    # ---- existing notified services ----

    def test_gta_to_body_corporate_is_rcm(self):
        res = self.guard.verify_rcm_applicability(
            ServiceType.GTA, EntityType.INDIVIDUAL, EntityType.BODY_CORPORATE
        )
        assert res["is_rcm"] is True
        assert res["liability"] == "RECIPIENT (RCM)"
        assert res["audit_trace"]["rule_id"] == "RCM_GTA"
        assert res["audit_trace"]["outcome"] == "REVERSE_CHARGE"

    def test_gta_to_individual_is_forward_charge(self):
        res = self.guard.verify_rcm_applicability(
            ServiceType.GTA, EntityType.INDIVIDUAL, EntityType.INDIVIDUAL
        )
        assert res["is_rcm"] is False
        assert res["liability"] == "PROVIDER (FCM)"
        assert res["audit_trace"]["rule_id"] == "RCM_NOT_APPLICABLE"
        assert res["audit_trace"]["outcome"] == "FORWARD_CHARGE"

    def test_legal_to_body_corporate_is_rcm(self):
        res = self.guard.verify_rcm_applicability(
            ServiceType.LEGAL, EntityType.INDIVIDUAL, EntityType.BODY_CORPORATE
        )
        assert res["is_rcm"] is True
        assert res["audit_trace"]["rule_id"] == "RCM_LEGAL"

    def test_legal_to_partnership_is_rcm(self):
        # A partnership firm is a "business entity" under Notification 13/2017
        # Sl. 2, so legal services to it also attract RCM.
        res = self.guard.verify_rcm_applicability(
            ServiceType.LEGAL, EntityType.INDIVIDUAL, EntityType.PARTNERSHIP
        )
        assert res["is_rcm"] is True
        assert res["audit_trace"]["rule_id"] == "RCM_LEGAL"

    def test_legal_to_individual_is_forward_charge(self):
        res = self.guard.verify_rcm_applicability(
            ServiceType.LEGAL, EntityType.INDIVIDUAL, EntityType.INDIVIDUAL
        )
        assert res["is_rcm"] is False

    def test_security_by_non_body_corporate_is_rcm(self):
        res = self.guard.verify_rcm_applicability(
            ServiceType.SECURITY, EntityType.INDIVIDUAL, EntityType.BODY_CORPORATE
        )
        assert res["is_rcm"] is True
        assert res["audit_trace"]["rule_id"] == "RCM_SECURITY"

    def test_security_by_body_corporate_is_forward_charge(self):
        # Provider is a body corporate -> no RCM.
        res = self.guard.verify_rcm_applicability(
            ServiceType.SECURITY, EntityType.BODY_CORPORATE, EntityType.BODY_CORPORATE
        )
        assert res["is_rcm"] is False

    # ---- newly added notified services ----

    def test_director_service_is_rcm(self):
        res = self.guard.verify_rcm_applicability(
            ServiceType.DIRECTOR, EntityType.INDIVIDUAL, EntityType.BODY_CORPORATE
        )
        assert res["is_rcm"] is True
        assert res["audit_trace"]["rule_id"] == "RCM_DIRECTOR"

    def test_director_service_to_non_body_corporate_is_forward_charge(self):
        res = self.guard.verify_rcm_applicability(
            ServiceType.DIRECTOR, EntityType.INDIVIDUAL, EntityType.PARTNERSHIP
        )
        assert res["is_rcm"] is False
        assert res["audit_trace"]["rule_id"] == "RCM_NOT_APPLICABLE"

    def test_sponsorship_to_body_corporate_is_rcm(self):
        res = self.guard.verify_rcm_applicability(
            ServiceType.SPONSORSHIP, EntityType.INDIVIDUAL, EntityType.BODY_CORPORATE
        )
        assert res["is_rcm"] is True
        assert res["audit_trace"]["rule_id"] == "RCM_SPONSORSHIP"

    def test_sponsorship_to_individual_is_forward_charge(self):
        res = self.guard.verify_rcm_applicability(
            ServiceType.SPONSORSHIP, EntityType.INDIVIDUAL, EntityType.INDIVIDUAL
        )
        assert res["is_rcm"] is False
        assert res["audit_trace"]["rule_id"] == "RCM_NOT_APPLICABLE"

    def test_renting_vehicle_by_non_body_corporate_is_rcm(self):
        res = self.guard.verify_rcm_applicability(
            ServiceType.RENTING_VEHICLE, EntityType.INDIVIDUAL, EntityType.BODY_CORPORATE
        )
        assert res["is_rcm"] is True
        assert res["audit_trace"]["rule_id"] == "RCM_RENTING_VEHICLE"

    def test_renting_vehicle_by_body_corporate_is_forward_charge(self):
        res = self.guard.verify_rcm_applicability(
            ServiceType.RENTING_VEHICLE,
            EntityType.BODY_CORPORATE,
            EntityType.BODY_CORPORATE,
        )
        assert res["is_rcm"] is False

    def test_import_service_is_always_rcm(self):
        res = self.guard.verify_rcm_applicability(
            ServiceType.IMPORT_SERVICE, EntityType.INDIVIDUAL, EntityType.INDIVIDUAL
        )
        assert res["is_rcm"] is True
        assert res["audit_trace"]["rule_id"] == "RCM_IMPORT_SERVICE"

    # ---- unknown / other ----

    def test_other_service_is_forward_charge(self):
        res = self.guard.verify_rcm_applicability(
            ServiceType.OTHER, EntityType.INDIVIDUAL, EntityType.BODY_CORPORATE
        )
        assert res["is_rcm"] is False
        assert res["audit_trace"]["rule_id"] == "RCM_NOT_APPLICABLE"

    def test_legacy_keys_preserved(self):
        # Backward compatibility: original keys must remain.
        res = self.guard.verify_rcm_applicability(
            ServiceType.GTA, EntityType.INDIVIDUAL, EntityType.BODY_CORPORATE
        )
        assert set(["verified", "liability", "is_rcm", "reason"]).issubset(res.keys())

    def test_accepts_raw_string_inputs(self):
        # JSON-sourced payloads pass raw strings; these must not crash and must
        # produce the same verdict as the enum members.
        res = self.guard.verify_rcm_applicability("GTA", "INDIVIDUAL", "BODY_CORPORATE")
        assert res["is_rcm"] is True
        assert res["audit_trace"]["inputs"]["service"] == "GTA"

    def test_unknown_string_service_fail_closed(self):
        """Unknown service type must fail closed (Issue #17) — no silent coercion to OTHER."""
        res = self.guard.verify_rcm_applicability("MYSTERY", "INDIVIDUAL", "BODY_CORPORATE")
        assert res["verified"] is False
        assert "Unknown service type" in res["error"]
        assert res["is_rcm"] is None

    def test_unknown_entity_fail_closed(self):
        """Unknown entity type must fail closed — no silent coercion to INDIVIDUAL."""
        res = self.guard.verify_rcm_applicability("DIRECTOR", "MYSTERY_ENTITY", "BODY_CORPORATE")
        assert res["verified"] is False
        assert "Unknown provider entity type" in res["error"]

    def test_list_value_fail_closed(self):
        """Malformed JSON value (list) must fail closed via TypeError catch."""
        res = self.guard.verify_rcm_applicability(["GTA"], "INDIVIDUAL", "BODY_CORPORATE")
        assert res["verified"] is False
        assert res["is_rcm"] is None

    # -- Dual-mode: verification mode vs computation mode --

    def test_verification_mode_match(self):
        """When claimed_is_rcm matches computed, verified=True."""
        res = self.guard.verify_rcm_applicability(
            ServiceType.GTA, EntityType.INDIVIDUAL, EntityType.BODY_CORPORATE,
            claimed_is_rcm=True,
        )
        assert res["verified"] is True
        assert res["is_rcm"] is True
        assert res["claimed_is_rcm"] is True

    def test_verification_mode_mismatch(self):
        """When claimed_is_rcm does not match computed, verified=False."""
        res = self.guard.verify_rcm_applicability(
            ServiceType.GTA, EntityType.INDIVIDUAL, EntityType.BODY_CORPORATE,
            claimed_is_rcm=False,
        )
        assert res["verified"] is False
        assert "RCM mismatch" in res["error"]

    def test_computation_mode_not_verified(self):
        """Without claimed_is_rcm, result is computed_only with verified=False (#18)."""
        res = self.guard.verify_rcm_applicability(
            ServiceType.GTA, EntityType.INDIVIDUAL, EntityType.BODY_CORPORATE,
        )
        assert res["verified"] is False
        assert res.get("computed_only") is True
        assert res["is_rcm"] is True
        assert "claimed_is_rcm" not in res

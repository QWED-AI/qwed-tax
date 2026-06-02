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

    def test_sponsorship_to_body_corporate_is_rcm(self):
        res = self.guard.verify_rcm_applicability(
            ServiceType.SPONSORSHIP, EntityType.INDIVIDUAL, EntityType.BODY_CORPORATE
        )
        assert res["is_rcm"] is True
        assert res["audit_trace"]["rule_id"] == "RCM_SPONSORSHIP"

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

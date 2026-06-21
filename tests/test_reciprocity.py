"""Tests for ReciprocityGuard fail-closed behavior (#40)."""

from qwed_tax.jurisdictions.us.reciprocity_guard import ReciprocityGuard
from qwed_tax.models import Address, State, WorkArrangement


class TestReciprocityGuard:
    def setup_method(self):
        self.guard = ReciprocityGuard()

    def test_same_state_verified(self):
        res = self.guard.verify_reciprocity("NY", "NY", same_state=True)
        assert res["verified"] is True
        assert res["withholding_state"] == State.NY

    def test_known_reciprocity_pair_verified(self):
        res = self.guard.verify_reciprocity("NJ", "PA", same_state=False)
        assert res["verified"] is True
        assert res["withholding_state"] == State.NJ

    def test_known_reciprocity_pair_reverse_verified(self):
        res = self.guard.verify_reciprocity("PA", "NJ", same_state=False)
        assert res["verified"] is True
        assert res["withholding_state"] == State.PA

    def test_no_reciprocity_blocked(self):
        res = self.guard.verify_reciprocity("NY", "TX", same_state=False)
        assert res["verified"] is False
        assert "No reciprocity agreement" in res["reason"]

    def test_unknown_state_pair_fail_closed(self):
        res = self.guard.verify_reciprocity("CA", "FL", same_state=False)
        assert res["verified"] is False

    def test_unknown_state_string_fail_closed(self):
        res = self.guard.verify_reciprocity("ZZ", "NY", same_state=False)
        assert res["verified"] is False
        assert "Unknown residence state" in res["message"]

    def test_invalid_state_type_fail_closed(self):
        res = self.guard.verify_reciprocity(123, "NY", same_state=False)
        assert res["verified"] is False

    def test_determine_withholding_state_same_state(self):
        addr = Address(street="1 Main St", city="Albany", state=State.NY, zip_code="12201")
        arrangement = WorkArrangement(
            employee_id="E1",
            residence_address=addr,
            work_address=addr,
        )
        res = self.guard.determine_withholding_state(arrangement)
        assert res["verified"] is True
        assert res["withholding_state"] == State.NY

    def test_determine_withholding_state_reciprocity(self):
        home = Address(street="1 Main St", city="Trenton", state=State.NJ, zip_code="08601")
        work = Address(street="2 Office Rd", city="Philly", state=State.PA, zip_code="19101")
        arrangement = WorkArrangement(
            employee_id="E1",
            residence_address=home,
            work_address=work,
        )
        res = self.guard.determine_withholding_state(arrangement)
        assert res["verified"] is True
        assert res["withholding_state"] == State.NJ

    def test_determine_withholding_state_no_reciprocity(self):
        home = Address(street="1 Main St", city="Albany", state=State.NY, zip_code="12201")
        work = Address(street="2 Office Rd", city="Austin", state=State.TX, zip_code="73301")
        arrangement = WorkArrangement(
            employee_id="E1",
            residence_address=home,
            work_address=work,
        )
        res = self.guard.determine_withholding_state(arrangement)
        assert res["verified"] is False

    def test_same_state_claim_mismatch_fail_closed(self):
        res = self.guard.verify_reciprocity("NY", "NJ", same_state=True)
        assert res["verified"] is False
        assert "conflicts" in res["message"]

    def test_same_state_claim_consistent_passes(self):
        res = self.guard.verify_reciprocity("NY", "NY", same_state=True)
        assert res["verified"] is True

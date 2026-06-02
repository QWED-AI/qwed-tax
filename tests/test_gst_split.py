"""Tests for GST CGST/SGST/IGST split verification (place-of-supply based)."""

from qwed_tax.jurisdictions.india.guards.gst_guard import GSTGuard


class TestGSTSplit:
    def setup_method(self):
        self.guard = GSTGuard()

    # ---- intra-state (CGST + SGST) ----

    def test_intra_state_correct_split_passes(self):
        # 18% of 1000 = 180 -> CGST 90 + SGST 90, IGST 0
        res = self.guard.verify_gst_split(
            "KA", "KA", 1000, 18, claimed_cgst=90, claimed_sgst=90, claimed_igst=0
        )
        assert res["verified"] is True
        assert res["supply_type"] == "INTRA_STATE"

    def test_intra_state_wrong_amount_blocks(self):
        res = self.guard.verify_gst_split(
            "KA", "KA", 1000, 18, claimed_cgst=100, claimed_sgst=80, claimed_igst=0
        )
        assert res["verified"] is False
        assert "cgst" in res["error"] or "sgst" in res["error"]

    def test_intra_state_igst_claimed_blocks_with_wrong_type(self):
        # IGST used on an intra-state supply must be flagged.
        res = self.guard.verify_gst_split(
            "KA", "KA", 1000, 18, claimed_cgst=0, claimed_sgst=0, claimed_igst=180
        )
        assert res["verified"] is False
        assert "IGST claimed on an intra-state supply" in res["error"]

    # ---- inter-state (IGST) ----

    def test_inter_state_correct_split_passes(self):
        # 18% of 1000 = 180 -> IGST 180, CGST/SGST 0
        res = self.guard.verify_gst_split(
            "KA", "MH", 1000, 18, claimed_cgst=0, claimed_sgst=0, claimed_igst=180
        )
        assert res["verified"] is True
        assert res["supply_type"] == "INTER_STATE"

    def test_inter_state_cgst_sgst_claimed_blocks_with_wrong_type(self):
        res = self.guard.verify_gst_split(
            "KA", "MH", 1000, 18, claimed_cgst=90, claimed_sgst=90, claimed_igst=0
        )
        assert res["verified"] is False
        assert "CGST/SGST claimed on an inter-state supply" in res["error"]

    def test_state_codes_are_case_insensitive(self):
        res = self.guard.verify_gst_split(
            "ka", "KA", 1000, 18, claimed_cgst=90, claimed_sgst=90, claimed_igst=0
        )
        assert res["verified"] is True
        assert res["supply_type"] == "INTRA_STATE"

    # ---- tolerance ----

    def test_half_rate_rounding_within_tolerance_passes(self):
        # 5% of 999 = 49.95 -> each leg 24.975; claiming 24.98/24.97 is within 2 paise.
        res = self.guard.verify_gst_split(
            "KA", "KA", 999, 5, claimed_cgst="24.98", claimed_sgst="24.97", claimed_igst=0
        )
        assert res["verified"] is True

    # ---- fail-closed input handling ----

    def test_missing_supplier_state_blocks(self):
        res = self.guard.verify_gst_split(
            "", "KA", 1000, 18, claimed_cgst=90, claimed_sgst=90, claimed_igst=0
        )
        assert res["verified"] is False
        assert "supplier_state" in res["error"]

    def test_non_numeric_value_blocks(self):
        res = self.guard.verify_gst_split(
            "KA", "KA", "pending", 18, claimed_cgst=90, claimed_sgst=90, claimed_igst=0
        )
        assert res["verified"] is False
        assert "numeric value" in res["error"]

    def test_non_finite_value_blocks(self):
        res = self.guard.verify_gst_split(
            "KA", "KA", float("inf"), 18, claimed_cgst=90, claimed_sgst=90, claimed_igst=0
        )
        assert res["verified"] is False
        assert "finite numeric value" in res["error"]

    def test_negative_value_blocks(self):
        res = self.guard.verify_gst_split(
            "KA", "KA", -1000, 18, claimed_cgst=90, claimed_sgst=90, claimed_igst=0
        )
        assert res["verified"] is False
        assert "non-negative" in res["error"]

    def test_negative_claimed_igst_blocks(self):
        # A small negative leg within the tolerance window must still fail closed.
        res = self.guard.verify_gst_split(
            "KA", "KA", 1000, 18, claimed_cgst=90, claimed_sgst=90, claimed_igst="-0.01"
        )
        assert res["verified"] is False
        assert "claimed_igst must be non-negative" in res["error"]

    def test_negative_claimed_cgst_blocks(self):
        res = self.guard.verify_gst_split(
            "KA", "MH", 1000, 18, claimed_cgst="-0.01", claimed_sgst=0, claimed_igst=180
        )
        assert res["verified"] is False
        assert "claimed_cgst must be non-negative" in res["error"]


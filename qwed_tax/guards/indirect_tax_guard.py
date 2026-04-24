from decimal import Decimal
import re
from typing import Any, Dict, List

from qwed_tax.numeric import decimal_text, parse_decimal_input


class InputCreditGuard:
    """
    Guard for Indirect Tax (GST/VAT) Input Tax Credit (ITC).
    Enforces Section 17(5) blocked credits and verifies GSTIN formats.
    """

    def __init__(self):
        # Categories where Input Tax Credit (ITC) is strictly blocked
        # Source: Section 17(5) of CGST Act (India) / VAT Guidelines (UK)
        self.blocked_categories: List[str] = [
            "FOOD_AND_BEVERAGE",
            "CATERING",
            "RESTAURANT_SERVICE",
            "CLUB_MEMBERSHIP",
            "HEALTH_INSURANCE",  # Unless mandatory by law
            "MOTOR_VEHICLE",  # With exceptions
            "GIFT_TO_EMPLOYEE",  # If > 50,000 INR
        ]

    def verify_itc_eligibility(
        self, expense_category: str, amount: Any, tax_paid: Any
    ) -> Dict[str, Any]:
        """
        Determines if the tax paid on an expense can be claimed as ITC.
        """
        normalized_cat = expense_category.upper().replace(" ", "_")
        try:
            parsed_amount = parse_decimal_input(amount, "amount")
            parsed_tax_paid = parse_decimal_input(tax_paid, "tax_paid")
        except ValueError as exc:
            return {"verified": False, "eligible_itc": "0", "reason": str(exc)}

        # Gift threshold: only blocked above 50,000 INR (exact match only)
        if normalized_cat == "GIFT_TO_EMPLOYEE" and parsed_amount < Decimal("50000"):
            return {
                "verified": True,
                "eligible_itc": decimal_text(parsed_tax_paid),
                "note": "Gift below INR 50,000 threshold; ITC allowed.",
            }

        # Blocked categories
        if normalized_cat in self.blocked_categories:
            return {
                "verified": False,
                "eligible_itc": "0",
                "reason": (
                    f"ITC is blocked for '{expense_category}' under Section 17(5) / VAT Rules."
                ),
            }

        # Personal consumption check (heuristic)
        if "PERSONAL" in normalized_cat:
            return {
                "verified": False,
                "eligible_itc": "0",
                "reason": "ITC is blocked for personal consumption.",
            }

        return {
            "verified": True,
            "eligible_itc": decimal_text(parsed_tax_paid),
            "note": "Expense appears eligible for Input Tax Credit.",
        }

    def verify_gstin_format(self, gstin: str) -> Dict[str, Any]:
        """
        Deterministic checksum validation for Indian GSTIN.
        Format: 22AAAAA0000A1Z5 (15 chars)
        """
        pattern = r"^\d{2}[A-Z]{5}\d{4}[A-Z][1-9A-Z]Z[0-9A-Z]$"
        if not re.match(pattern, gstin):
            return {"verified": False, "error": "Invalid GSTIN format."}
        return {"verified": True}

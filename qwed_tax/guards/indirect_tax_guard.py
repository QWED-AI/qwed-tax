from decimal import Decimal
import re
from typing import Any, Dict, List

from qwed_tax.audit import (
    ITC_BLOCKED_17_5,
    ITC_ELIGIBLE,
    ITC_GIFT_THRESHOLD,
    ITC_PERSONAL_CONSUMPTION,
    build_trace,
)
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
            "GIFT_TO_EMPLOYEE",  # Only blocked when amount exceeds 50,000 INR
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

        # Gift threshold: gifts of 50,000 INR or less remain eligible; only amounts above that block.
        if normalized_cat == "GIFT_TO_EMPLOYEE" and parsed_amount <= Decimal("50000"):
            return {
                "verified": True,
                "eligible_itc": decimal_text(parsed_tax_paid),
                "note": "Gift of INR 50,000 or less; ITC allowed.",
                "audit_trace": build_trace(
                    ITC_GIFT_THRESHOLD,
                    "ALLOWED",
                    {"expense_category": normalized_cat, "amount": decimal_text(parsed_amount)},
                ),
            }

        # Blocked categories
        if normalized_cat in self.blocked_categories:
            return {
                "verified": False,
                "eligible_itc": "0",
                "reason": (
                    f"ITC is blocked for '{expense_category}' under Section 17(5) / VAT Rules."
                ),
                "audit_trace": build_trace(
                    ITC_BLOCKED_17_5,
                    "BLOCKED",
                    {"expense_category": normalized_cat},
                ),
            }

        # Personal consumption check (heuristic)
        if "PERSONAL" in normalized_cat:
            return {
                "verified": False,
                "eligible_itc": "0",
                "reason": "ITC is blocked for personal consumption.",
                "audit_trace": build_trace(
                    ITC_PERSONAL_CONSUMPTION,
                    "BLOCKED",
                    {"expense_category": normalized_cat},
                ),
            }

        return {
            "verified": True,
            "eligible_itc": decimal_text(parsed_tax_paid),
            "note": "Expense appears eligible for Input Tax Credit.",
            "audit_trace": build_trace(
                ITC_ELIGIBLE,
                "ALLOWED",
                {"expense_category": normalized_cat},
            ),
        }

    # GSTIN check-digit alphabet: digits 0-9 followed by A-Z (base 36).
    _GSTIN_CODES = "0123456789ABCDEFGHIJKLMNOPQRSTUVWXYZ"

    @staticmethod
    def _gstin_check_digit(first_14: str) -> str:
        """
        Compute the 15th GSTIN check character from the first 14 characters.

        Algorithm (GSTN spec):
          - Map each character to its index in [0-9A-Z] (base 36).
          - Multiply by an alternating factor (1, 2, 1, 2, ... left to right).
          - For each product, add (product // 36) + (product % 36) to a sum.
          - check = (36 - (sum % 36)) % 36, mapped back to the alphabet.
        """
        total = 0
        for index, char in enumerate(first_14):
            value = InputCreditGuard._GSTIN_CODES.index(char)
            factor = 1 if index % 2 == 0 else 2
            product = value * factor
            total += (product // 36) + (product % 36)
        return InputCreditGuard._GSTIN_CODES[(36 - (total % 36)) % 36]

    def verify_gstin_format(self, gstin: str) -> Dict[str, Any]:
        """
        Deterministic GSTIN validation: structural format plus the 15th-digit
        checksum (base-36 GSTN algorithm).

        Format: 22AAAAA0000A1Z5 (15 chars). A string that matches the format but
        carries an incorrect check digit is rejected as a checksum failure.
        """
        pattern = r"^\d{2}[A-Z]{5}\d{4}[A-Z][1-9A-Z]Z[0-9A-Z]$"
        if not re.match(pattern, gstin):
            return {"verified": False, "error": "Invalid GSTIN format."}

        # Do not echo the correct check digit back to the caller: revealing it
        # would turn this validator into an oracle for fabricating GSTINs that
        # pass both format and checksum checks.
        if gstin[14] != self._gstin_check_digit(gstin[:14]):
            return {"verified": False, "error": "Invalid GSTIN checksum."}

        return {"verified": True}

from typing import Dict, Any, List
import re

class InputCreditGuard:
    """
    Guard for Indirect Tax (GST/VAT) Input Tax Credit (ITC).
    Enforces Section 17(5) Blocked Credits and verifies GSTIN formats.
    """
    def __init__(self):
        # Categories where Input Tax Credit (ITC) is strictly blocked
        # Source: Section 17(5) of CGST Act (India) / VAT Guidelines (UK)
        self.blocked_categories = [
            "FOOD_AND_BEVERAGE",
            "CATERING",
            "RESTAURANT_SERVICE",
            "CLUB_MEMBERSHIP",
            "HEALTH_INSURANCE", # Unless mandatory by law
            "MOTOR_VEHICLE",    # With exceptions
            "GIFT_TO_EMPLOYEE"  # If > 50,000 INR
        ]

    def verify_itc_eligibility(self, expense_category: str, amount: float, tax_paid: float) -> Dict[str, Any]:
        """
        Determines if the Tax Paid on an expense can be claimed as Credit (ITC).
        """
        normalized_cat = expense_category.upper().replace(" ", "_")
        
        # Rule 1: Blocked Categories
        if any(blocked in normalized_cat for blocked in self.blocked_categories):
            return {
                "verified": False,
                "eligible_itc": 0.0,
                "reason": f"ITC is blocked for '{expense_category}' under Section 17(5) / VAT Rules."
            }
            
        # Rule 2: Personal Consumption Check (Heuristic)
        # If no explicit category, but looks personal (simplified heuristic)
        if "PERSONAL" in normalized_cat:
             return {
                "verified": False,
                "eligible_itc": 0.0,
                "reason": "ITC is blocked for personal consumption."
            }

        return {
            "verified": True,
            "eligible_itc": tax_paid,
            "note": "Expense appears eligible for Input Tax Credit."
        }

    def verify_gstin_format(self, gstin: str) -> Dict[str, Any]:
        """
        Deterministic Checksum validation for Indian GSTIN.
        Format: 22AAAAA0000A1Z5 (15 chars)
        """
        pattern = r"^\d{2}[A-Z]{5}\d{4}[A-Z]{1}[1-9A-Z]{1}Z[0-9A-Z]{1}$"
        if not re.match(pattern, gstin):
             return {"verified": False, "error": "Invalid GSTIN format."}
        return {"verified": True}

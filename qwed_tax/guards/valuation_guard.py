from decimal import Decimal, InvalidOperation, DivisionByZero
from typing import Dict, Any

class ValuationGuard:
    """
    Deterministic Guard for Startup Conversions (Convertible Notes/SAFEs).
    Verifies Pre-Money vs Post-Money share price math.
    """

    def verify_conversion(self, investment: str, cap: str, discount: str, next_round_price: str) -> Dict[str, Any]:
        """
        Verifies share conversion price for startups.
        Math: Price = min(Cap_Price, Next_Round_Price * (1 - Discount))
        """
        try:
            d_cap = Decimal(cap)
            d_next = Decimal(next_round_price)
            d_disc = Decimal(discount)
            d_inv = Decimal(investment)
        except InvalidOperation:
             return {"verified": False, "error": "Invalid numerical input for valuation."}

        if not (Decimal("0") <= d_disc < Decimal("1")):
            return {"verified": False, "error": "Discount must be between 0 and 1."}
        if d_cap <= 0 or d_next <= 0 or d_inv <= 0:
            return {"verified": False, "error": "Cap, next round price, and investment must be positive."}

        discounted_price = d_next * (1 - d_disc)
        final_price = min(d_cap, discounted_price)
        method = "CAP" if final_price == d_cap else "DISCOUNT"

        try:
            shares = d_inv / final_price
        except (DivisionByZero, InvalidOperation):
            return {"verified": False, "error": "Final price resolved to zero — cannot compute shares."}

        return {
            "verified": True,
            "deterministic_price": str(final_price),
            "shares_issued": str(shares),
            "method": method
        }

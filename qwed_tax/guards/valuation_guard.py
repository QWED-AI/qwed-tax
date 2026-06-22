from decimal import Decimal, InvalidOperation, DivisionByZero
from typing import Any, Dict

from qwed_tax.audit import SAFE_CONVERSION, build_trace
from qwed_tax.diagnostics import TaxDiagnosticResult

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
             return {
                 "verified": False,
                 "error": "Invalid numerical input for valuation.",
                 "audit_trace": build_trace(SAFE_CONVERSION, "INVALID_INPUT", {"investment": investment, "cap": cap, "discount": discount, "next_round_price": next_round_price}),
             }

        if not (Decimal("0") <= d_disc < Decimal("1")):
            return {
                "verified": False,
                "error": "Discount must be between 0 and 1.",
                "audit_trace": build_trace(SAFE_CONVERSION, "INVALID_DISCOUNT", {"discount": discount}),
            }
        if d_cap <= 0 or d_next <= 0 or d_inv <= 0:
            return {
                "verified": False,
                "error": "Cap, next round price, and investment must be positive.",
                "audit_trace": build_trace(SAFE_CONVERSION, "NON_POSITIVE_INPUT", {"cap": cap, "next_round_price": next_round_price, "investment": investment}),
            }

        discounted_price = d_next * (1 - d_disc)
        final_price = min(d_cap, discounted_price)
        method = "CAP" if final_price == d_cap else "DISCOUNT"

        try:
            shares = d_inv / final_price
        except (DivisionByZero, InvalidOperation):
            return {
                "verified": False,
                "error": "Final price resolved to zero — cannot compute shares.",
                "audit_trace": build_trace(SAFE_CONVERSION, "ZERO_PRICE", {"final_price": str(final_price)}),
            }

        return {
            "verified": True,
            "deterministic_price": str(final_price),
            "shares_issued": str(shares),
            "method": method,
            "audit_trace": build_trace(SAFE_CONVERSION, "CONVERSION_VERIFIED", {"investment": investment, "cap": cap, "discount": discount, "next_round_price": next_round_price, "final_price": str(final_price), "method": method}),
        }

    @staticmethod
    def to_diagnostic(result: Dict[str, Any]) -> TaxDiagnosticResult:
        """Convert a legacy verify_conversion() dict to TaxDiagnosticResult."""
        verified = result.get("verified", False)
        audit_trace = result.get("audit_trace")

        if not verified:
            return TaxDiagnosticResult.blocked(
                agent_message="Valuation verification could not be completed.",
                developer_fields={
                    "constraint_id": audit_trace["rule_id"] if audit_trace else "SAFE_CONVERSION_UNKNOWN",
                    "audit_trace": audit_trace,
                    "error": result.get("error"),
                },
            )

        if audit_trace is None:
            raise ValueError(
                "VERIFIED result requires audit_trace — "
                "use UNVERIFIABLE if no evidence was established."
            )

        return TaxDiagnosticResult.verified(
            agent_message="Valuation verified.",
            developer_fields={
                "constraint_id": audit_trace["rule_id"],
                "statute": audit_trace.get("statute"),
                "jurisdiction": audit_trace.get("jurisdiction"),
                "audit_trace": audit_trace,
                "deterministic_price": result.get("deterministic_price"),
                "shares_issued": result.get("shares_issued"),
                "method": result.get("method"),
            },
            evidence=audit_trace,
        )

from decimal import Decimal
from typing import Any, Dict

from qwed_tax.audit import FEMA_SCHEDULE_I, LRS_LIMIT, build_trace
from qwed_tax.diagnostics import TaxDiagnosticResult
from qwed_tax.numeric import decimal_text, parse_decimal_input

class RemittanceGuard:
    """
    Deterministic Guard for Cross-Border Transactions (FEMA/RBI/LRS).
    Enforces Liberalised Remittance Scheme (LRS) limits and Tax Collected at Source (TCS).
    """

    def verify_lrs_limit(self, amount_usd: Any, purpose: str, financial_year_usage: Any) -> Dict[str, Any]:
        """
        Verifies Liberalised Remittance Scheme (LRS) limits.
        Returns a verification report dict and fails closed on invalid numeric inputs.
        Source: Audit Trace 3253e38e9d60
        """
        limit = Decimal("250000") # $250k annual limit
        try:
            current_txn = parse_decimal_input(amount_usd, "amount_usd")
            usage = parse_decimal_input(financial_year_usage, "financial_year_usage")
        except ValueError as exc:
            return {
                "verified": False,
                "error": f"BLOCKED: {exc}",
                "audit_trace": build_trace(LRS_LIMIT, "INVALID_INPUT", {"amount_usd": str(amount_usd), "financial_year_usage": str(financial_year_usage)}),
            }

        if current_txn < 0:
            return {
                "verified": False,
                "error": "BLOCKED: Remittance amount must be non-negative.",
                "audit_trace": build_trace(LRS_LIMIT, "NEGATIVE_AMOUNT", {"amount_usd": decimal_text(current_txn)}),
            }
        if usage < 0:
            return {
                "verified": False,
                "error": "BLOCKED: Financial year usage must be non-negative.",
                "audit_trace": build_trace(LRS_LIMIT, "NEGATIVE_USAGE", {"financial_year_usage": decimal_text(usage)}),
            }
        
        # 1. Prohibited Transactions Check (Schedule I)
        prohibited_purposes = ["GAMBLING", "LOTTERY", "RACING", "BANNED_MAGAZINES", "SWEEPSTAKES", "MARGIN_TRADING"]
        if any(p in purpose.upper() for p in prohibited_purposes):
            return {
                "verified": False,
                "error": f"BLOCKED: Remittance for '{purpose}' is strictly prohibited under FEMA Schedule I.",
                "audit_trace": build_trace(FEMA_SCHEDULE_I, "PROHIBITED", {"purpose": purpose}),
            }

        # 2. Limit Check
        if (usage + current_txn) > limit:
             return {
                "verified": False,
                 "error": (
                     "BLOCKED: Transaction exceeds LRS limit ($250,000). "
                     f"Remaining: ${decimal_text(limit - usage)}"
                 ),
                 "audit_trace": build_trace(LRS_LIMIT, "LIMIT_EXCEEDED", {"amount_usd": decimal_text(current_txn), "usage": decimal_text(usage), "limit": decimal_text(limit)}),
             }
            
        return {
            "verified": True,
            "audit_trace": build_trace(LRS_LIMIT, "WITHIN_LIMIT", {"amount_usd": decimal_text(current_txn), "usage": decimal_text(usage), "limit": decimal_text(limit)}),
        }

    @staticmethod
    def to_diagnostic(result: Dict[str, Any]) -> TaxDiagnosticResult:
        """Convert a legacy verify_lrs_limit() dict to TaxDiagnosticResult."""
        verified = result.get("verified", False)
        audit_trace = result.get("audit_trace")

        if not verified:
            return TaxDiagnosticResult.blocked(
                agent_message="Remittance verification could not be completed.",
                developer_fields={
                    "constraint_id": audit_trace["rule_id"] if audit_trace else "LRS_UNKNOWN",
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
            agent_message="Remittance verified.",
            developer_fields={
                "constraint_id": audit_trace["rule_id"],
                "statute": audit_trace.get("statute"),
                "jurisdiction": audit_trace.get("jurisdiction"),
                "audit_trace": audit_trace,
            },
            evidence=audit_trace,
        )

    def calculate_tcs(self, amount_inr: Any, purpose: str, is_loan_funded: bool = False) -> Decimal:
        """
        Deterministically calculates Tax Collected at Source (TCS).
        Rule: Education (Loan) = 0.5%, Education (Self) = 5%, Other = 20%
        Returns a Decimal and raises ValueError on invalid numeric input.
        """
        amt = parse_decimal_input(amount_inr, "amount_inr")
        threshold = Decimal("700000") # 7 Lakhs exemption
        
        if amt <= threshold:
            return Decimal("0")
            
        taxable_amount = amt - threshold
        
        p = purpose.upper()
        if "EDUCATION" in p:
            rate = Decimal("0.005") if is_loan_funded else Decimal("0.05")
        elif "MEDICAL" in p:
            rate = Decimal("0.05")
        else:
            rate = Decimal("0.20") # New 20% rule for tours/investments (Oct 1 2023)
            
        return taxable_amount * rate

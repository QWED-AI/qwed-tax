from decimal import Decimal
from typing import Any, Dict

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
            return {"verified": False, "error": f"BLOCKED: {exc}"}

        if current_txn < 0:
            return {"verified": False, "error": "BLOCKED: Remittance amount must be non-negative."}
        if usage < 0:
            return {"verified": False, "error": "BLOCKED: Financial year usage must be non-negative."}
        
        # 1. Prohibited Transactions Check (Schedule I)
        prohibited_purposes = ["GAMBLING", "LOTTERY", "RACING", "BANNED_MAGAZINES", "SWEEPSTAKES", "MARGIN_TRADING"]
        if any(p in purpose.upper() for p in prohibited_purposes):
            return {
                "verified": False,
                "error": f"BLOCKED: Remittance for '{purpose}' is strictly prohibited under FEMA Schedule I."
            }

        # 2. Limit Check
        if (usage + current_txn) > limit:
             return {
                "verified": False,
                 "error": (
                     "BLOCKED: Transaction exceeds LRS limit ($250,000). "
                     f"Remaining: ${decimal_text(limit - usage)}"
                 )
             }
            
        return {"verified": True}

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

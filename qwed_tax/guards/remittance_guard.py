from decimal import Decimal
from typing import Dict, Any, List

class RemittanceGuard:
    """
    Deterministic Guard for Cross-Border Transactions (FEMA/RBI/LRS).
    Enforces Liberalised Remittance Scheme (LRS) limits and Tax Collected at Source (TCS).
    """

    def verify_lrs_limit(self, amount_usd: float, purpose: str, financial_year_usage: float) -> Dict[str, Any]:
        """
        Verifies Liberalised Remittance Scheme (LRS) limits.
        Source: Audit Trace 3253e38e9d60
        """
        limit = Decimal("250000") # $250k annual limit
        current_txn = Decimal(str(amount_usd))
        usage = Decimal(str(financial_year_usage))
        
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
                "error": f"BLOCKED: Transaction exceeds LRS limit ($250,000). Remaining: ${limit - usage}"
            }
            
        return {"verified": True}

    def calculate_tcs(self, amount_inr: float, purpose: str, is_loan_funded: bool = False) -> Decimal:
        """
        Deterministically calculates Tax Collected at Source (TCS).
        Rule: Education (Loan) = 0.5%, Education (Self) = 5%, Other = 20%
        """
        amt = Decimal(str(amount_inr))
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

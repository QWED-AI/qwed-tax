from typing import Dict, Any

class RelatedPartyGuard:
    """
    Deterministic Guard for Related Party Transactions (Corporate Compliance).
    Enforces Companies Act (e.g., India Sec 185, US SOX) restrictions on loans to directors.
    """

    def verify_loan_compliance(self, lender_type: str, borrower_role: str, interest_rate: float, market_rate: float) -> Dict[str, Any]:
        """
        Deterministic verification of Loans to Directors (Section 185).
        """
        # Prohibited Roles (Companies Act 2013 Sec 185 / Generic Corporate Governance)
        prohibited_roles = ["DIRECTOR", "DIRECTOR_RELATIVE", "PARTNER", "PARTNER_OF_DIRECTOR", "HOLDING_COMPANY_DIRECTOR"]
        
        borrower_clean = borrower_role.upper().replace(" ", "_")
        
        # Rule 1: Absolute Prohibition (unless exempted)
        if any(role in borrower_clean for role in prohibited_roles):
            # Check Exemptions would go here (e.g. is_managing_director & employee_scheme)
            # For now, default to BLOCK high risk.
            return {
                "verified": False,
                "risk": "SECTION_185_VIOLATION",
                "message": f"Loans to {borrower_role} are prohibited under Section 185 unless specific exemptions apply (MD/WTD + Employee Scheme)."
            }
            
        # Rule 2: Interest Rate Benchmarking (Section 186)
        # Corporate loans must yield at least Gov Security / Market Rate
        if interest_rate < market_rate:
             return {
                "verified": False,
                "risk": "SECTION_186_VIOLATION",
                "message": f"Interest rate {interest_rate}% is below market yield {market_rate}%. Must charge commercial rate."
            }
            
        return {"verified": True, "note": "Loan compliance verified."}

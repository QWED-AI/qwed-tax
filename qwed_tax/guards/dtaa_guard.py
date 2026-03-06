from typing import Dict, Any
from decimal import Decimal

class DTAAGuard:
    """
    Deterministic Guard for Double Taxation Avoidance Agreements (DTAA).
    Verifies Foreign Tax Credit (FTC) claims under Article 23 (Methods for Elimination of Double Taxation).
    """
    
    def verify_foreign_tax_credit(self, 
                                foreign_income: float,
                                foreign_tax_paid: float,
                                home_tax_rate: float,
                                foreign_tax_limit_rate: float = 15.0) -> Dict[str, Any]:
        """
        Verify Foreign Tax Credit (FTC) availability.
        Rule: Credit is Lower of (Actual Foreign Tax Paid) OR (Tax Payable in Home Country on that income).
        
        Args:
            foreign_income: Income earned in source country.
            foreign_tax_paid: Actual tax withheld/paid in source country.
            home_tax_rate: Tax rate applicable in resident country (home).
            foreign_tax_limit_rate: Max tax rate allowed under DTAA (e.g., 15% for dividends/royalty).
        """
        f_income = Decimal(str(foreign_income))
        f_tax_paid = Decimal(str(foreign_tax_paid))
        h_rate = Decimal(str(home_tax_rate)) / Decimal("100")
        f_limit_rate = Decimal(str(foreign_tax_limit_rate)) / Decimal("100")
        
        # 1. Tax Payable in Home Country on foreign income
        home_tax_payable = f_income * h_rate
        
        # 2. DTAA Treaty Limit — max creditable tax under treaty rate
        treaty_limit = f_income * f_limit_rate
        
        # 3. Allowable Credit = Min(Foreign Tax Paid, Home Tax Payable, Treaty Limit)
        allowable_credit = min(f_tax_paid, home_tax_payable, treaty_limit)
        
        if allowable_credit < f_tax_paid:
             return {
                "verified": True, # It is verified, but capped.
                "message": f"FTC Capped. Paid {f_tax_paid}, but allowable credit is {allowable_credit} (Home: {home_tax_payable}, Treaty: {treaty_limit}).",
                "allowable_credit": float(allowable_credit),
                "excess_tax_lapsed": float(f_tax_paid - allowable_credit)
            }
            
        return {
            "verified": True,
            "message": "Full Foreign Tax Credit allowed.",
            "allowable_credit": float(allowable_credit),
            "excess_tax_lapsed": 0.0
        }

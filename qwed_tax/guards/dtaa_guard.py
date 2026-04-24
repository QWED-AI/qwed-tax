from decimal import Decimal
from typing import Any, Dict, Optional

from qwed_tax.numeric import decimal_text, parse_decimal_input

PERCENT_BASE = Decimal("100")

class DTAAGuard:
    """
    Deterministic Guard for Double Taxation Avoidance Agreements (DTAA).
    Verifies Foreign Tax Credit (FTC) claims under Article 23 (Methods for Elimination of Double Taxation).
    """
    
    def verify_foreign_tax_credit(self, 
                                foreign_income: Any,
                                foreign_tax_paid: Any,
                                home_tax_rate: Any,
                                foreign_tax_limit_rate: Optional[Any] = None) -> Dict[str, Any]:
        """
        Verify Foreign Tax Credit (FTC) availability.
        Rule: Credit is Lower of (Actual Foreign Tax Paid) OR (Tax Payable in Home Country on that income).
        
        Args:
            foreign_income: Income earned in source country.
            foreign_tax_paid: Actual tax withheld/paid in source country.
            home_tax_rate: Tax rate applicable in resident country (home).
            foreign_tax_limit_rate: Max tax rate allowed under DTAA (e.g., 15% for dividends/royalty).
        """
        try:
            f_income = parse_decimal_input(foreign_income, "foreign_income")
            f_tax_paid = parse_decimal_input(foreign_tax_paid, "foreign_tax_paid")
            h_rate = parse_decimal_input(home_tax_rate, "home_tax_rate") / PERCENT_BASE
        except ValueError as exc:
            return {
                "verified": False,
                "message": str(exc),
                "allowable_credit": "0",
                "excess_tax_lapsed": "0",
            }
        
        # 1. Tax Payable in Home Country on foreign income
        home_tax_payable = f_income * h_rate
        
        # 2. Allowable Credit = Min(Foreign Tax Paid, Home Tax Payable)
        allowable_credit = min(f_tax_paid, home_tax_payable)
        
        # 3. DTAA Treaty Limit — only applied when treaty rate is provided
        if foreign_tax_limit_rate is not None:
            try:
                f_limit_rate = parse_decimal_input(
                    foreign_tax_limit_rate, "foreign_tax_limit_rate"
                ) / PERCENT_BASE
            except ValueError as exc:
                return {
                    "verified": False,
                    "message": str(exc),
                    "allowable_credit": "0",
                    "excess_tax_lapsed": "0",
                }
            treaty_limit = f_income * f_limit_rate
            allowable_credit = min(allowable_credit, treaty_limit)
        
        if allowable_credit < f_tax_paid:
            msg = (
                f"FTC Capped. Paid {decimal_text(f_tax_paid)}, allowable credit is "
                f"{decimal_text(allowable_credit)} (Home: {decimal_text(home_tax_payable)})."
            )
            if foreign_tax_limit_rate is not None:
                msg = (
                    f"FTC Capped. Paid {decimal_text(f_tax_paid)}, allowable credit is "
                    f"{decimal_text(allowable_credit)} (Home: {decimal_text(home_tax_payable)}, "
                    f"Treaty: {decimal_text(treaty_limit)})."
                )
            return {
                "verified": True,
                "message": msg,
                "allowable_credit": decimal_text(allowable_credit),
                "excess_tax_lapsed": decimal_text(f_tax_paid - allowable_credit)
            }
            
        return {
            "verified": True,
            "message": "Full Foreign Tax Credit allowed.",
            "allowable_credit": decimal_text(allowable_credit),
            "excess_tax_lapsed": "0"
        }

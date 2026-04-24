from decimal import Decimal, ROUND_HALF_UP
from typing import Any, Dict

from qwed_tax.numeric import decimal_text, parse_decimal_input

RATIO_SCALE = Decimal("0.0001")

class PoEMGuard:
    """
    Deterministic Guard for Place of Effective Management (PoEM).
    Used to determine tax residency of foreign companies.
    Ref: CBDT Circular 6 of 2017 (India), OECD Models.
    """
    
    def determine_residency(self, 
                          company_name: str,
                          is_foreign_incorp: bool,
                          turnover_total: Any,
                          turnover_outside_india: Any,
                          assets_total: Any,
                          assets_outside_india: Any,
                          employees_total: int,
                          employees_outside_india: int,
                          payroll_total: Any,
                          payroll_outside_india: Any,
                          key_management_location: str) -> Dict[str, Any]:
        """
        Determine if a foreign company is a Resident via PoEM.
        
        Rule (India):
        Foreign Company is Resident IF:
        1. Numeric turnover, asset, and payroll fields are well-formed.
        2. Fails "Active Business Outside India" (ABOI) test.
           ABOI Criteria (ALL must be true):
           - Assets Outside India >= 50%
           - Employees Outside India >= 50%
           - Payroll Outside India >= 50%
           
        AND
        3. Place of Effective Management is in India.
        """
        
        if not is_foreign_incorp:
            return {"verified": True, "residency": "RESIDENT", "reason": "Incorporated in India"}

        try:
            # Turnover fields are currently validated for input-shape hygiene only; ABOI uses asset, employee, and payroll ratios.
            _ = parse_decimal_input(turnover_total, "turnover_total")
            _ = parse_decimal_input(turnover_outside_india, "turnover_outside_india")
            parsed_assets_total = parse_decimal_input(assets_total, "assets_total")
            parsed_assets_outside = parse_decimal_input(assets_outside_india, "assets_outside_india")
            parsed_payroll_total = parse_decimal_input(payroll_total, "payroll_total")
            parsed_payroll_outside = parse_decimal_input(payroll_outside_india, "payroll_outside_india")
        except ValueError as exc:
            return {
                "verified": False,
                "residency": "UNVERIFIABLE",
                "reason": str(exc),
            }
        if employees_total < 0 or employees_outside_india < 0:
            return {
                "verified": False,
                "residency": "UNVERIFIABLE",
                "reason": "employee counts must be non-negative integers.",
            }
        if employees_outside_india > employees_total:
            return {
                "verified": False,
                "residency": "UNVERIFIABLE",
                "reason": "employees_outside_india cannot exceed employees_total.",
            }

        # ABOI Test Checks
        # Note: 'Passive Income' check requires P&L data, here we simplify to Asset/Emp ratios as critical proxy.
        
        raw_assets_ratio = (
            parsed_assets_outside / parsed_assets_total if parsed_assets_total > Decimal("0") else Decimal("0")
        )
        raw_emp_ratio = (
            Decimal(employees_outside_india) / Decimal(employees_total)
            if employees_total > 0
            else Decimal("0")
        )
        raw_payroll_ratio = (
            parsed_payroll_outside / parsed_payroll_total
            if parsed_payroll_total > Decimal("0")
            else Decimal("0")
        )
        assets_ratio = raw_assets_ratio.quantize(RATIO_SCALE, rounding=ROUND_HALF_UP).normalize()
        emp_ratio = raw_emp_ratio.quantize(RATIO_SCALE, rounding=ROUND_HALF_UP).normalize()
        payroll_ratio = raw_payroll_ratio.quantize(RATIO_SCALE, rounding=ROUND_HALF_UP).normalize()
        
        is_aboi = (
            raw_assets_ratio >= Decimal("0.50")
            and raw_emp_ratio >= Decimal("0.50")
            and raw_payroll_ratio >= Decimal("0.50")
        )
        
        if is_aboi:
            # If Active Business is Outside India, PoEM is presumed Outside UNLESS majority board meetings in India.
            # For this guard, if ABOI is True, we generally treat as NON_RESIDENT unless forced.
            residency = "NON_RESIDENT"
            reason = "Company satisfies Active Business Outside India (ABOI) test."
        else:
            # Failed ABOI. Residency depends on Key Management Location.
            if key_management_location.upper() == "INDIA":
                residency = "RESIDENT"
                reason = "Fails ABOI test AND Key Management is in India (PoEM established)."
            else:
                residency = "NON_RESIDENT" # Even if fails ABOI, if decisions taken outside, then Non-Resident.
                reason = "Fails ABOI test BUT Key Management is Outside India."

        return {
            "verified": True,
            "residency": residency,
            "is_aboi": is_aboi,
            "metrics": {
                "assets_outside_ratio": decimal_text(assets_ratio),
                "employees_outside_ratio": decimal_text(emp_ratio),
                "payroll_outside_ratio": decimal_text(payroll_ratio),
            },
            "reason": reason
        }

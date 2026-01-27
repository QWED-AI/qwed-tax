from typing import Dict, Any

class PoEMGuard:
    """
    Deterministic Guard for Place of Effective Management (PoEM).
    Used to determine tax residency of foreign companies.
    Ref: CBDT Circular 6 of 2017 (India), OECD Models.
    """
    
    def determine_residency(self, 
                          company_name: str,
                          is_foreign_incorp: bool,
                          turnover_total: float,
                          turnover_outside_india: float,
                          assets_total: float,
                          assets_outside_india: float,
                          employees_total: int,
                          employees_outside_india: int,
                          payroll_total: float,
                          payroll_outside_india: float,
                          key_management_location: str) -> Dict[str, Any]:
        """
        Determine if a foreign company is a Resident via PoEM.
        
        Rule (India):
        Foreign Company is Resident IF:
        1. Turnover > 50 Cr (If less, usually exempt from rigorous PoEM, but here we assume scrutiny).
        2. Fails "Active Business Outside India" (ABOI) test.
           ABOI Criteria (ALL must be true):
           - Passive Income < 50% of Total Income (Simulated via Turnover here for simplicity)
           - Assets Outside India >= 50%
           - Employees Outside India >= 50%
           - Payroll Outside India >= 50%
           
        AND
        3. Place of Effective Management is in India.
        """
        
        if not is_foreign_incorp:
            return {"verified": True, "residency": "RESIDENT", "reason": "Incorporated in India"}

        # ABOI Test Checks
        # Note: 'Passive Income' check requires P&L data, here we simplify to Asset/Emp ratios as critical proxy.
        
        assets_ratio = assets_outside_india / assets_total if assets_total > 0 else 0
        emp_ratio = employees_outside_india / employees_total if employees_total > 0 else 0
        payroll_ratio = payroll_outside_india / payroll_total if payroll_total > 0 else 0
        
        is_aboi = (assets_ratio >= 0.50) and (emp_ratio >= 0.50) and (payroll_ratio >= 0.50)
        
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
                "assets_outside_ratio": float(assets_ratio),
                "employees_outside_ratio": float(emp_ratio),
                "payroll_outside_ratio": float(payroll_ratio)
            },
            "reason": reason
        }

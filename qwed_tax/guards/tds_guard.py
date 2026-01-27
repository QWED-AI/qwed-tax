from decimal import Decimal
from typing import Dict, Any

class TDSGuard:
    """
    Guard for Tax Deducted at Source (TDS) / Withholding Tax.
    Enforces deduction rates based on service type and thresholds.
    """
    def __init__(self):
        # 2025 TDS Thresholds & Rates (Simplified based on India Income Tax Act)
        # Rates are strict Decimal to avoid float errors
        self.tds_rules = {
            "PROFESSIONAL_FEES": {"threshold": 30000, "rate": Decimal("0.10")}, # Sec 194J
            "CONTRACTOR_INDIVIDUAL": {"threshold": 30000, "rate": Decimal("0.01")}, # Sec 194C
            "CONTRACTOR_FIRM": {"threshold": 30000, "rate": Decimal("0.02")},       # Sec 194C
            "COMMISSION": {"threshold": 15000, "rate": Decimal("0.05")},            # Sec 194H
            "RENT_LAND": {"threshold": 240000, "rate": Decimal("0.10")}             # Sec 194I
        }

    def calculate_deduction(self, service_type: str, invoice_amount: float, ytd_payment: float) -> Dict[str, Any]:
        """
        Verifies if TDS must be deducted before paying the vendor.
        """
        rule = self.tds_rules.get(service_type.upper().replace(" ", "_"))
        if not rule:
            return {"verified": True, "deduction": "0", "note": "No TDS rule found for category"}

        inv_amt = Decimal(str(invoice_amount))
        ytd_amt = Decimal(str(ytd_payment))
        
        total_exposure = inv_amt + ytd_amt
        threshold = Decimal(str(rule["threshold"]))
        
        # Logic: If total YTD exposure (including current invoice) crosses threshold, deduct TDS.
        # Usually TDS is on the entire amount once threshold is crossed, but for simplicity here
        # we apply to current invoice. In rigorous systems, we'd catch up previous undeducted too.
        if total_exposure > threshold:
            deduction = inv_amt * rule["rate"]
            return {
                "verified": True,
                "deduction": str(deduction),
                "net_payable": str(inv_amt - deduction),
                "section": service_type
            }
            
        return {"verified": True, "deduction": "0", "net_payable": str(inv_amt)}

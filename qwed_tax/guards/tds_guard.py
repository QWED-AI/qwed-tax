from decimal import Decimal
from typing import Any, Dict

from qwed_tax.audit import TDS_194C, TDS_194H, TDS_194I, TDS_194J, build_trace
from qwed_tax.numeric import decimal_text, parse_decimal_input

class TDSGuard:
    """
    Guard for Tax Deducted at Source (TDS) / Withholding Tax.
    Enforces deduction rates based on service type and thresholds.
    """
    def __init__(self):
        # 2025 TDS Thresholds & Rates (Simplified based on India Income Tax Act)
        # Rates are strict Decimal to avoid float errors
        self.tds_rules = {
            "PROFESSIONAL_FEES": {"threshold": Decimal("30000"), "rate": Decimal("0.10"), "rule": TDS_194J},
            "CONTRACTOR_INDIVIDUAL": {"threshold": Decimal("30000"), "rate": Decimal("0.01"), "rule": TDS_194C},
            "CONTRACTOR_FIRM": {"threshold": Decimal("30000"), "rate": Decimal("0.02"), "rule": TDS_194C},
            "COMMISSION": {"threshold": Decimal("15000"), "rate": Decimal("0.05"), "rule": TDS_194H},
            "RENT_LAND": {"threshold": Decimal("240000"), "rate": Decimal("0.10"), "rule": TDS_194I},
        }

    def calculate_deduction(self, service_type: str, invoice_amount: Any, ytd_payment: Any) -> Dict[str, Any]:
        """
        Verifies if TDS must be deducted before paying the vendor.
        """
        rule = self.tds_rules.get(service_type.upper().replace(" ", "_"))
        if not rule:
            return {"verified": True, "deduction": "0", "note": "No TDS rule found for category"}

        try:
            inv_amt = parse_decimal_input(invoice_amount, "invoice_amount")
            ytd_amt = parse_decimal_input(ytd_payment, "ytd_payment")
        except ValueError as exc:
            return {
                "verified": False,
                "error": str(exc),
            }
        
        total_exposure = inv_amt + ytd_amt
        threshold = rule["threshold"]
        
        # Logic: If total YTD exposure (including current invoice) crosses threshold, deduct TDS.
        # Usually TDS is on the entire amount once threshold is crossed, but for simplicity here
        # we apply to current invoice. In rigorous systems, we'd catch up previous undeducted too.
        if total_exposure > threshold:
            deduction = inv_amt * rule["rate"]
            return {
                "verified": True,
                "deduction": decimal_text(deduction),
                "net_payable": decimal_text(inv_amt - deduction),
                "section": service_type,
                "audit_trace": build_trace(
                    rule["rule"],
                    "DEDUCTION_REQUIRED",
                    {
                        "service_type": service_type.upper().replace(" ", "_"),
                        "total_exposure": decimal_text(total_exposure),
                        "threshold": decimal_text(threshold),
                    },
                ),
            }

        return {
            "verified": True,
            "deduction": "0",
            "net_payable": decimal_text(inv_amt),
            "audit_trace": build_trace(
                rule["rule"],
                "BELOW_THRESHOLD",
                {
                    "service_type": service_type.upper().replace(" ", "_"),
                    "total_exposure": decimal_text(total_exposure),
                    "threshold": decimal_text(threshold),
                },
            ),
        }

from decimal import Decimal
from ...models import ContractorPayment, PaymentType

# Threshold table: payment_type -> (form, threshold)
_FILING_RULES = {
    PaymentType.NON_EMPLOYEE_COMPENSATION: ("1099-NEC", Decimal("600.00")),
    PaymentType.RENT: ("1099-MISC", Decimal("600.00")),
    PaymentType.ROYALTIES: ("1099-MISC", Decimal("10.00")),
    PaymentType.ATTORNEY_FEES: ("1099-MISC", Decimal("600.00")),
}

class Form1099Guard:
    """
    Verifies IRS 1099 Filing Requirements.
    Determines if logic requires filing 1099-NEC or 1099-MISC.
    """
    
    def verify_filing_requirement(self, payment: ContractorPayment):
        """
        Returns which form (if any) is required based on payment type and amount.
        Reference: IRS Instructions for Forms 1099-MISC and 1099-NEC.
        """
        amount = payment.amount
        ptype = payment.payment_type
        
        rule = _FILING_RULES.get(ptype)
        if rule is None:
            return {
                "filing_required": False,
                "form": None,
                "reason": f"No filing rule defined for payment type '{ptype}'."
            }

        form_name, threshold = rule
        if amount >= threshold:
            return {
                "filing_required": True,
                "form": form_name,
                "reason": f"{ptype.value} (${amount}) >= ${threshold}"
            }

        return {
            "filing_required": False,
            "form": None,
            "reason": f"{ptype.value} (${amount}) below threshold (${threshold})"
        }

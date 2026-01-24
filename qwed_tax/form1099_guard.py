from decimal import Decimal
from .models import ContractorPayment, PaymentType

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
        
        # Thresholds (2024/2025 Standard)
        NEC_THRESHOLD = Decimal("600.00")
        RENT_THRESHOLD = Decimal("600.00")
        ROYALTY_THRESHOLD = Decimal("10.00")
        ATTORNEY_THRESHOLD = Decimal("600.00")
        
        required_form = None
        reason = ""
        
        if ptype == PaymentType.NON_EMPLOYEE_COMPENSATION:
            if amount >= NEC_THRESHOLD:
                required_form = "1099-NEC"
                reason = f"Non-employee compensation (${amount}) >= ${NEC_THRESHOLD}"
            else:
                reason = f"Non-employee compensation (${amount}) below threshold (${NEC_THRESHOLD})"

        elif ptype == PaymentType.RENT:
            if amount >= RENT_THRESHOLD:
                required_form = "1099-MISC"
                reason = f"Rent payments (${amount}) >= ${RENT_THRESHOLD}"
            else:
                reason = "Rent below threshold"

        elif ptype == PaymentType.ROYALTIES:
            if amount >= ROYALTY_THRESHOLD:
                required_form = "1099-MISC"
                reason = f"Royalties (${amount}) >= ${ROYALTY_THRESHOLD}"
            else:
                reason = "Royalties below threshold"
                
        elif ptype == PaymentType.ATTORNEY_FEES:
            # Gross proceeds to an attorney
            if amount >= ATTORNEY_THRESHOLD:
                required_form = "1099-MISC" # Box 10 usually, or NEC depending on service. keeping simple.
                reason = f"Attorney fees (${amount}) >= ${ATTORNEY_THRESHOLD}"
            else:
                reason = "Attorney fees below threshold"
                
        return {
            "filing_required": required_form is not None,
            "form": required_form,
            "reason": reason
        }

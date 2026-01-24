from decimal import Decimal, getcontext
from .models import PayrollEntry, VerificationResult

# Set precision high enough for currency
getcontext().prec = 28

class PayrollGuard:
    """
    Verifies the mathematical accuracy of payroll calculations.
    Ensures that Gross Pay - Taxes - Deductions == Net Pay exactly.
    """
    
    def verify_gross_to_net(self, entry: PayrollEntry) -> VerificationResult:
        """
        Verifies that net pay matches the sum of its parts.
        """
        gross = entry.gross_pay
        
        # Calculate total tax
        total_tax = sum((t.amount for t in entry.taxes), Decimal("0.00"))
        
        # Calculate total deductions
        total_deductions = sum((d.amount for d in entry.deductions), Decimal("0.00"))
        
        # Deterministic recalculation
        calculated_net = gross - total_tax - total_deductions
        
        # Check discrepancy
        discrepancy = calculated_net - entry.net_pay_claimed
        
        if discrepancy == Decimal("0.00"):
            return VerificationResult(
                verified=True,
                recalculated_net_pay=calculated_net,
                discrepancy=discrepancy,
                message="✅ VERIFIED: Net Pay matches Gross - Taxes - Deductions."
            )
        else:
            return VerificationResult(
                verified=False,
                recalculated_net_pay=calculated_net,
                discrepancy=discrepancy,
                message=f"❌ ERROR: Mathematical discrepancy detected. Claimed Net: {entry.net_pay_claimed}, Calculated: {calculated_net}. Diff: {discrepancy}"
            )

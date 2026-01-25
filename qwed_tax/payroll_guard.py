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

    def verify_fica_tax(self, gross_ytd: Decimal, current_gross: Decimal, claimed_ss_tax: Decimal) -> VerificationResult:
        """
        Verifies Social Security Tax (6.2%) stops at 2025 Wage Base Limit ($176,100).
        """
        SS_RATE = Decimal("0.062")
        SS_LIMIT = Decimal("176100.00")
        
        # Calculate taxable amount for this period
        previous_ytd = gross_ytd - current_gross
        
        # If already capped
        if previous_ytd >= SS_LIMIT:
            expected_tax = Decimal("0.00")
            msg_suffix = "(Already hit YTD Limit)"
        
        # If capping in this check
        elif gross_ytd > SS_LIMIT:
            taxable_portion = SS_LIMIT - previous_ytd
            expected_tax = taxable_portion * SS_RATE
            msg_suffix = f"(Hit Limit this period. Taxable: ${taxable_portion})"
            
        # Normal
        else:
            expected_tax = current_gross * SS_RATE
            msg_suffix = ""
            
        # Round to 2 decimals
        expected_tax = expected_tax.quantize(Decimal("0.01"))
        
        if claimed_ss_tax == expected_tax:
            return VerificationResult(
                verified=True, recalculated_net_pay=Decimal(0), discrepancy=Decimal(0),
                message=f"✅ FICA Tax Correct: ${expected_tax} {msg_suffix}"
            )
        else:
            diff = claimed_ss_tax - expected_tax
            return VerificationResult(
                verified=False, recalculated_net_pay=Decimal(0), discrepancy=diff,
                message=f"❌ FICA Error: Expected ${expected_tax}, Claimed ${claimed_ss_tax}. Limit logic failed? {msg_suffix}"
            )

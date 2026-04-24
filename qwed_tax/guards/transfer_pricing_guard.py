from decimal import Decimal
from typing import Any, Dict

from qwed_tax.numeric import decimal_text, parse_decimal_input

class TransferPricingGuard:
    """
    Deterministic Guard for Cross-Border / Related Party Pricing (Arm's Length Price).
    Ref: OECD Guidelines, US Sec 482, India Sec 92C.
    """
    
    def verify_arms_length_price(self, 
                               transaction_price: Any, 
                               benchmark_price: Any, 
                               method: str = "CUP", 
                               tolerance_percent: Any = "3.0") -> Dict[str, Any]:
        """
        Verify if a transaction price is within the 'Arm's Length' range.
        
        Args:
            transaction_price: The actual price charged to/by related party.
            benchmark_price: The Arm's Length Price (ALP) determined by analysis.
            method: Transfer Pricing Method used (e.g., CUP - Comparable Uncontrolled Price).
            tolerance_percent: Safe harbour tolerance (e.g., India allows 1% or 3%).
        """
        try:
            tx_price = parse_decimal_input(transaction_price, "transaction_price")
            alp_price = parse_decimal_input(benchmark_price, "benchmark_price")
            tolerance = parse_decimal_input(tolerance_percent, "tolerance_percent") / Decimal("100")
        except ValueError as exc:
            return {
                "verified": False,
                "risk": "INVALID_NUMERIC_INPUT",
                "message": str(exc),
                "safe_harbour_range": [],
                "potential_adjustment": "0",
            }
        
        # Calculate Safe Harbour Range
        # Lower bound = ALP * (1 - tolerance)
        # Upper bound = ALP * (1 + tolerance)
        
        lower_bound = alp_price * (Decimal("1") - tolerance)
        upper_bound = alp_price * (Decimal("1") + tolerance)
        
        if lower_bound <= tx_price <= upper_bound:
            return {
                "verified": True,
                "message": (
                    f"Transaction price {decimal_text(tx_price)} is within Safe Harbour range "
                    f"({decimal_text(lower_bound)} - {decimal_text(upper_bound)}) of ALP {decimal_text(alp_price)}."
                ),
                "safe_harbour_range": [decimal_text(lower_bound), decimal_text(upper_bound)],
                "potential_adjustment": "0",
            }
        else:
            # Adjustment Required (Primary Adjustment)
            # Typically, tax authorities adjust TO the ALP, not the bound.
            adjustment = alp_price - tx_price
            
            # Logic depends on whether it's income or expense. 
            # Assuming 'transaction_price' is Income received. 
            # If Expense paid, logic inverts. 
            # For simplicity in this guard, we flag deviation magnitude.
            
            return {
                "verified": False,
                "risk": "TRANSFER_PRICING_ADJUSTMENT",
                "message": (
                    f"Price {decimal_text(tx_price)} deviates from ALP {decimal_text(alp_price)} "
                    f"beyond {decimal_text(tolerance * Decimal('100'))}% tolerance."
                ),
                "safe_harbour_range": [decimal_text(lower_bound), decimal_text(upper_bound)],
                "potential_adjustment": decimal_text(adjustment),
            }

from typing import Dict, Any, Optional
from decimal import Decimal

class TransferPricingGuard:
    """
    Deterministic Guard for Cross-Border / Related Party Pricing (Arm's Length Price).
    Ref: OECD Guidelines, US Sec 482, India Sec 92C.
    """
    
    def verify_arms_length_price(self, 
                               transaction_price: float, 
                               benchmark_price: float, 
                               method: str = "CUP", 
                               tolerance_percent: float = 3.0) -> Dict[str, Any]:
        """
        Verify if a transaction price is within the 'Arm's Length' range.
        
        Args:
            transaction_price: The actual price charged to/by related party.
            benchmark_price: The Arm's Length Price (ALP) determined by analysis.
            method: Transfer Pricing Method used (e.g., CUP - Comparable Uncontrolled Price).
            tolerance_percent: Safe harbour tolerance (e.g., India allows 1% or 3%).
        """
        tx_price = Decimal(str(transaction_price))
        alp_price = Decimal(str(benchmark_price))
        tolerance = Decimal(str(tolerance_percent)) / Decimal("100")
        
        # Calculate Safe Harbour Range
        # Lower bound = ALP * (1 - tolerance)
        # Upper bound = ALP * (1 + tolerance)
        
        lower_bound = alp_price * (Decimal("1") - tolerance)
        upper_bound = alp_price * (Decimal("1") + tolerance)
        
        if lower_bound <= tx_price <= upper_bound:
            return {
                "verified": True,
                "message": f"Transaction price {tx_price} is within Safe Harbour range ({lower_bound} - {upper_bound}) of ALP {alp_price}.",
                "adjustment_required": 0.0
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
                "message": f"Price {tx_price} deviates from ALP {alp_price} beyond {tolerance_percent}% tolerance.",
                "safe_harbour_range": [float(lower_bound), float(upper_bound)],
                "potential_adjustment": float(adjustment)
            }

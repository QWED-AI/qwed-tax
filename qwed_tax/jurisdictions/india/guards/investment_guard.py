from z3 import *
from enum import Enum
from pydantic import BaseModel

class TransactionType(str, Enum):
    INTRADAY = "INTRADAY"
    DELIVERY = "DELIVERY"
    F_O = "F_O" # Futures & Options

class InvestmentGuard:
    """
    Verifies Classification of Stock Market Income for Indian Tax.
    Key Distinction: Intraday is SPECULATIVE BUSINESS INCOME (Slab Rate).
                     Delivery is CAPITAL GAINS (10%/15%).
    Source: Audit Trace 26525cd2c6b6
    """
    
    def verify_classification(self, tx_type: TransactionType, holding_period_days: int) -> dict:
        """
        Uses Z3 to determine the correct tax head.
        """
        s = Solver()
        
        # Variables
        is_intraday = Bool('is_intraday')
        is_delivery = Bool('is_delivery')
        
        # Outputs (Tax Heads)
        tax_head_speculative = Bool('head_speculative_business')
        tax_head_capital_gains = Bool('head_capital_gains')
        
        # Rules
        # Rule 1: Intraday is ALWAYS Speculative Business (Sec 43(5))
        s.add(Implies(is_intraday, tax_head_speculative))
        
        # Rule 2: Delivery is Capital Gains
        s.add(Implies(is_delivery, tax_head_capital_gains))
        
        # Rule 3: Mutually Exclusive Heads (Simplified)
        s.add(Not(And(tax_head_speculative, tax_head_capital_gains)))
        
        # Add Input Facts
        s.add(is_intraday == (tx_type == TransactionType.INTRADAY))
        s.add(is_delivery == (tx_type == TransactionType.DELIVERY))
        
        # Check
        if s.check() == sat:
            m = s.model()
            is_spec = is_true(m[tax_head_speculative])
            is_cg = is_true(m[tax_head_capital_gains])
            
            if is_spec:
                return {
                    "classification": "Speculative Business Income",
                    "tax_treatment": "Added to Total Income (Slab Rate)",
                    "verified": True
                }
            elif is_cg:
                term = "LTCG" if holding_period_days > 365 else "STCG"
                return {
                    "classification": f"Capital Gains ({term})",
                    "tax_treatment": "Special Rates (10%/12.5% or 15%/20%)",
                    "verified": True
                }
            else:
                 return {"classification": "Unknown", "verified": False}
        else:
             return {"classification": "Logic Error", "verified": False}

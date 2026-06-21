from enum import Enum

class TaxHead(str, Enum):
    SALARY = "SALARY"
    HOUSE_PROPERTY = "HOUSE_PROPERTY"
    BUSINESS_NON_SPECULATIVE = "BUSINESS_NON_SPECULATIVE"
    BUSINESS_SPECULATIVE = "BUSINESS_SPECULATIVE" # Intraday
    CAPITAL_GAINS_LT = "CAPITAL_GAINS_LT"
    CAPITAL_GAINS_ST = "CAPITAL_GAINS_ST"
    OTHER_SOURCES = "OTHER_SOURCES"
    VDA = "VDA" # Crypto

class InterHeadAdjustmentGuard:
    """
    Verifies Inter-Head Set-off of Losses.
    Source: Audit Trace 26525cd2c6b6, 9fcb7f59948a
    """
    
    # The Matrix of Prohibitions
    # Key: The Loss Source
    # Value: List of Heads it CANNOT be set off against
    PROHIBITED_SETOFFS = {
        TaxHead.BUSINESS_SPECULATIVE: [
            TaxHead.SALARY, TaxHead.HOUSE_PROPERTY, TaxHead.BUSINESS_NON_SPECULATIVE, 
            TaxHead.CAPITAL_GAINS_LT, TaxHead.CAPITAL_GAINS_ST, TaxHead.OTHER_SOURCES
        ], # Speculative loss only against Speculative profit
        
        TaxHead.CAPITAL_GAINS_LT: [
            TaxHead.SALARY, TaxHead.HOUSE_PROPERTY, TaxHead.BUSINESS_NON_SPECULATIVE,
            TaxHead.BUSINESS_SPECULATIVE, TaxHead.OTHER_SOURCES, TaxHead.CAPITAL_GAINS_ST # LT Loss only against LT Gain
        ],
        
        TaxHead.CAPITAL_GAINS_ST: [
            TaxHead.SALARY, TaxHead.HOUSE_PROPERTY, TaxHead.BUSINESS_NON_SPECULATIVE,
            TaxHead.BUSINESS_SPECULATIVE, TaxHead.OTHER_SOURCES
        ], # ST Loss can be against ST or LT Gain (so LT is allowed, not prohibited)
        
        TaxHead.VDA: ["ALL"], # Special case: Crypto loss dead ends.

        TaxHead.SALARY: ["ALL"], # Salary losses cannot be set off against any other head.
    }

    # Heads explicitly known to have no inter-head set-off restrictions
    # (their losses can be set off against any profit head per Indian tax law)
    _EXPLICITLY_ALLOWED_LOSS_HEADS = {
        TaxHead.HOUSE_PROPERTY,
        TaxHead.BUSINESS_NON_SPECULATIVE,
        TaxHead.OTHER_SOURCES,
    }

    def verify_setoff(self, loss_head: TaxHead, profit_head: TaxHead) -> dict:
        """
        Verifies if setting off loss from 'loss_head' against profit from 'profit_head' is legal.
        """
        # 1. Check if Loss Head has restrictions
        if loss_head in self.PROHIBITED_SETOFFS:
            restrictions = self.PROHIBITED_SETOFFS[loss_head]
            
            # 2. Check "ALL" condition
            if "ALL" in restrictions:
                 return {
                    "verified": False,
                    "message": f"❌ Illegal Set-Off: Loss from {loss_head.value} cannot be set off against anything (it lapses)."
                }
            
            # 3. Check specific prohibition
            if profit_head in restrictions:
                 return {
                    "verified": False,
                    "message": f"❌ Illegal Set-Off: Loss from {loss_head.value} cannot be set off against {profit_head.value}."
                }

            # Loss head is in the prohibition matrix but this specific pair is not prohibited
            return {
                "verified": True,
                "message": f"✅ Allowed: {loss_head.value} loss set off against {profit_head.value}."
            }

        # 4. Check if head is explicitly allowed (no restrictions per tax law)
        if loss_head not in self._EXPLICITLY_ALLOWED_LOSS_HEADS:
            return {
                "verified": False,
                "message": (
                    f"Loss head {loss_head.value} is not in the configured prohibition matrix "
                    "or allowlist. Cannot verify set-off legality — manual review required."
                ),
            }

        # If no restriction found and head is explicitly allowed, it's allowed
        return {
            "verified": True,
            "message": f"✅ Allowed: {loss_head.value} loss set off against {profit_head.value}."
        }

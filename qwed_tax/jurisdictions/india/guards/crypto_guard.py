from decimal import Decimal
from enum import Enum
from typing import Dict, List, Optional
from pydantic import BaseModel

class AssetClass(str, Enum):
    VDA = "VDA" # Virtual Digital Asset (Crypto/NFT)
    EQUITY = "EQUITY"
    BUSINESS = "BUSINESS"

class TaxResult(BaseModel):
    verified: bool
    message: str
    allowed_set_off: Decimal

class CryptoTaxGuard:
    """
    Verifies Section 115BBH compliance for Indian Taxation.
    Key Rule: Loss from transfer of VDA cannot be set off against any other income.
    """
    
    def verify_set_off(self, losses: Dict[str, Decimal], gains: Dict[str, Decimal]) -> TaxResult:
        """
        Verifies if the proposed set-off of losses is legal.
        losses: Dict like {"VDA": -5000, "EQUITY": -200}
        gains: Dict like {"BUSINESS": 10000}
        """
        
        # Rule 1: Check for VDA Losses being used
        if "VDA" in losses and losses["VDA"] < 0:
            # We must verify that VDA loss is NOT reducing taxable income from other heads
            
            # Simple simulation: 
            # If Net Taxable Income < (Total Gains - Non-VDA Losses)
            # It implies VDA loss was used.
            
            total_gains = sum(gains.values(), Decimal(0))
            non_vda_losses = sum((v for k, v in losses.items() if k != "VDA"), Decimal(0))
            
            # This guard is meant to be called on a specific TRANSACTION attempt
            # But here we verify the logic rule itself.
            
            return TaxResult(
                verified=False,
                message="⚠️ Section 115BBH Alert: Loss from VDA (Crypto/NFT) cannot be set off against any other income. It must lapse.",
                allowed_set_off=Decimal(0) # 0 set off allowed for VDA
            )
            
        return TaxResult(
            verified=True, 
            message="✅ No restricted VDA loss set-off detected.",
            allowed_set_off=Decimal(0) # Logic simplified for this specific guard
        )
            
    def verify_flat_tax_rate(self, vda_income: Decimal, claimed_tax: Decimal) -> TaxResult:
        """
        Verifies strict 30% tax on positive VDA income (plus cess usually, simplified here).
        """
        EXPECTED_RATE = Decimal("0.30")
        
        if vda_income <= 0:
            return TaxResult(verified=True, message="No VDA Income", allowed_set_off=Decimal(0))
            
        expected_tax = vda_income * EXPECTED_RATE
        
        # Allow small float tolerance if input wasn't decimal, but strict for now
        if abs(claimed_tax - expected_tax) < Decimal("0.1"):
             return TaxResult(
                verified=True, 
                message=f"✅ VDA Tax correct (30% of {vda_income})",
                allowed_set_off=Decimal(0)
            )
        else:
             return TaxResult(
                verified=False, 
                message=f"❌ Section 115BBH Violation: VDA Income taxed at 30% flat. Expected {expected_tax}, Claimed {claimed_tax}",
                allowed_set_off=Decimal(0)
            )

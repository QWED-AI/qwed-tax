from typing import Optional
from .jurisdictions.us.payroll_guard import PayrollGuard
from .jurisdictions.us.classification_guard import ClassificationGuard
from .jurisdictions.india.guards.crypto_guard import CryptoTaxGuard
from .jurisdictions.india.guards.investment_guard import InvestmentGuard
from .jurisdictions.india.guards.gst_guard import GSTGuard
from .jurisdictions.india.guards.deposit_guard import DepositRateGuard
from .jurisdictions.india.guards.setoff_guard import InterHeadAdjustmentGuard

class TaxVerifier:
    """
    The main entry point for QWED-Tax.
    Orchestrates guards based on jurisdiction.
    """
    
    def __init__(self, jurisdiction: str = "US"):
        self.jurisdiction = jurisdiction.upper()
        
        # Initialize Guards lazy-loaded or all-at-once
        if self.jurisdiction == "US":
            self.payroll = PayrollGuard()
            self.classification = ClassificationGuard()
        elif self.jurisdiction == "INDIA":
            self.crypto = CryptoTaxGuard()
            self.investment = InvestmentGuard()
            self.gst = GSTGuard()
            self.deposit = DepositRateGuard()
            self.setoff = InterHeadAdjustmentGuard()
        else:
            raise ValueError(f"Unsupported Jurisdiction: {jurisdiction}")

    def verify_us_payroll(self, **kwargs):
        if self.jurisdiction != "US": raise ValueError("Switch to US jurisdiction")
        return self.payroll.verify_gross_to_net(kwargs.get('entry'))

    def verify_india_crypto(self, losses, gains):
        if self.jurisdiction != "INDIA": raise ValueError("Switch to INDIA jurisdiction")
        return self.crypto.verify_set_off(losses, gains)

    def verify_india_deposit(self, **kwargs):
        if self.jurisdiction != "INDIA": raise ValueError("Switch to INDIA jurisdiction")
        return self.deposit.verify_fd_rate(**kwargs)

from typing import Optional, Dict, Any
from .jurisdictions.us.payroll_guard import PayrollGuard
# New Guards are in .guards package as per recent update
from .guards.classification_guard import ClassificationGuard
from .guards.nexus_guard import NexusGuard

# India Guards
from .jurisdictions.india.guards.crypto_guard import CryptoTaxGuard
from .jurisdictions.india.guards.investment_guard import InvestmentGuard
from .jurisdictions.india.guards.gst_guard import GSTGuard
from .jurisdictions.india.guards.deposit_guard import DepositRateGuard
from .jurisdictions.india.guards.setoff_guard import InterHeadAdjustmentGuard

class TaxPreFlight:
    """
    The 'Swiss Cheese' Defense Layer for Agentic Finance.
    Runs generic deterministic checks (Classification, Nexus) BEFORE
    heavy payroll or logic execution.
    """
    def __init__(self):
        self.classifier = ClassificationGuard()
        self.nexus = NexusGuard()
        # self.payroll = PayrollGuard() # Can be added if needed

    def audit_transaction(self, intent: Dict[str, Any]) -> Dict[str, Any]:
        """
        The 'Pre-Flight' Check for Agentic Finance.
        intent = {
            "action": "pay_invoice",
            "worker_type": "1099",
            "state": "NY",
            "sales_data": {"amount": 600000},
            "worker_facts": {...}
            ...
        }
        """
        report = {"allowed": True, "blocks": []}

        # Check 1: Worker Classification
        if "worker_facts" in intent and "worker_type" in intent:
            class_check = self.classifier.verify_classification_claim(
                intent["worker_type"], intent["worker_facts"]
            )
            if not class_check["verified"]:
                report["allowed"] = False
                report["blocks"].append(class_check["error"])

        # Check 2: Economic Nexus
        if "sales_data" in intent and "state" in intent:
            # Default to "no_tax" decision if not provided, to trigger check if threshold crossed
            tax_decision = intent.get("tax_decision", "no_tax")
            nexus_check = self.nexus.check_nexus_liability(
                intent["state"], 
                intent["sales_data"].get("amount", 0), 
                intent["sales_data"].get("transactions", 0), 
                tax_decision
            )
            if not nexus_check["verified"]:
                report["allowed"] = False
                report["blocks"].append(nexus_check["error"])

        return report

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
            self.preflight = TaxPreFlight() # Include preflight for US
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

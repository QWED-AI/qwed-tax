from .guards.speculation_guard import SpeculationGuard
from .guards.capital_gains_guard import CapitalGainsGuard
from .guards.related_party_guard import RelatedPartyGuard
from .guards.valuation_guard import ValuationGuard
from .guards.remittance_guard import RemittanceGuard

class TaxPreFlight:
    """
    The 'Swiss Cheese' Defense Layer for Agentic Finance.
    Runs generic deterministic checks (Classification, Nexus) BEFORE
    heavy payroll or logic execution.
    """
    def __init__(self):
        self.classifier = ClassificationGuard()
        self.nexus = NexusGuard()
        self.speculation = SpeculationGuard()
        self.cg = CapitalGainsGuard()
        self.related_party = RelatedPartyGuard()
        self.valuation = ValuationGuard()
        self.remittance = RemittanceGuard()

    def audit_transaction(self, intent: Dict[str, Any]) -> Dict[str, Any]:
        """
        The 'Pre-Flight' Check for Agentic Finance.
        intent = {
            "action": "pay_invoice" | "trade_tax" | "corporate_action" | "remit_money",
            ...
        }
        """
        report = {"allowed": True, "blocks": []}

        # Check 1: Worker Classification (Payroll)
        if "worker_facts" in intent and "worker_type" in intent:
            class_check = self.classifier.verify_classification_claim(
                intent["worker_type"], intent["worker_facts"]
            )
            if not class_check["verified"]:
                report["allowed"] = False
                report["blocks"].append(class_check["error"])

        # Check 2: Economic Nexus (Sales)
        if "sales_data" in intent and "state" in intent:
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

        # Check 3: Trader Set-Off (Investments)
        if "loss_head" in intent and "offset_head" in intent:
            setoff = self.speculation.verify_setoff(
                intent["loss_head"], 
                intent.get("loss_amount", 0), 
                intent["offset_head"]
            )
            if not setoff["verified"]:
                report["allowed"] = False
                report["blocks"].append(setoff["error"] + " " + setoff.get("fix", ""))

        # Check 4: Capital Gains Rates (Investments)
        if "asset_type" in intent and "dates" in intent:
            dates = intent["dates"]
            term = self.cg.determine_term(dates["buy"], dates["sell"], intent["asset_type"])
            if "claimed_rate" in intent:
                rate_check = self.cg.verify_tax_rate(intent["asset_type"], term, intent["claimed_rate"])
                if not rate_check["verified"]:
                    report["allowed"] = False
                    report["blocks"].append(rate_check["error"])

        # Check 5: Corporate Loans (Section 185)
        if "lender_type" in intent and "borrower_role" in intent:
             loan_check = self.related_party.verify_loan_compliance(
                 intent["lender_type"], 
                 intent["borrower_role"], 
                 intent.get("interest_rate", 0), 
                 intent.get("market_rate", 0)
             )
             if not loan_check["verified"]:
                 report["allowed"] = False
                 report["blocks"].append(loan_check["message"])

        # Check 6: Startup Valuation (Convertible Notes)
        if "investment_round" in intent and intent["investment_round"] == "convertible_note":
             val_check = self.valuation.verify_conversion(
                 intent.get("investment_amount", "0"),
                 intent.get("cap_price", "0"), # Assumes Price Cap
                 intent.get("discount", "0"),
                 intent.get("next_round_price", "0")
             )
             if not val_check["verified"]:
                 report["allowed"] = False
                 report["blocks"].append(val_check["error"])

        # Check 7: International Remittance (LRS/TCS)
        if "remittance_amount_usd" in intent and "purpose" in intent:
             remit_check = self.remittance.verify_lrs_limit(
                 intent["remittance_amount_usd"],
                 intent["purpose"],
                 intent.get("fy_usage", 0)
             )
             if not remit_check["verified"]:
                 report["allowed"] = False
                 report["blocks"].append(remit_check["error"])

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

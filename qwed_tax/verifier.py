from typing import Dict, Any
from decimal import Decimal
from .guards.speculation_guard import SpeculationGuard
from .guards.capital_gains_guard import CapitalGainsGuard
from .guards.related_party_guard import RelatedPartyGuard
from .guards.valuation_guard import ValuationGuard
from .guards.remittance_guard import RemittanceGuard
from .guards.indirect_tax_guard import InputCreditGuard
from .guards.tds_guard import TDSGuard
from .guards.classification_guard import ClassificationGuard
from .guards.nexus_guard import NexusGuard
from .jurisdictions.us.payroll_guard import PayrollGuard
from .jurisdictions.india.guards.crypto_guard import CryptoTaxGuard
from .jurisdictions.india.guards.investment_guard import InvestmentGuard
from .jurisdictions.india.guards.gst_guard import GSTGuard
from .jurisdictions.india.guards.deposit_guard import DepositRateGuard

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
        self.indirect_tax = InputCreditGuard()
        self.withholding = TDSGuard()

    def audit_transaction(self, intent: Dict[str, Any]) -> Dict[str, Any]:
        """
        The 'Pre-Flight' Check for Agentic Finance.
        intent = {
            "action": "pay_invoice" | "trade_tax" | "corporate_action" | "remit_money" | "expense_claim",
            ...
        }
        """
        report = {"allowed": True, "blocks": []}

        self._check_worker_classification(intent, report)
        self._check_economic_nexus(intent, report)
        self._check_trader_setoff(intent, report)
        self._check_capital_gains(intent, report)
        self._check_corporate_loans(intent, report)
        self._check_startup_valuation(intent, report)
        self._check_international_remittance(intent, report)
        self._check_expense_and_tds(intent, report)

        return report

    # ---- extracted checks (each keeps complexity flat) ----

    def _check_worker_classification(self, intent: Dict[str, Any], report: Dict[str, Any]) -> None:
        if "worker_facts" not in intent or "worker_type" not in intent:
            return
        class_check = self.classifier.verify_classification_claim(
            intent["worker_type"], intent["worker_facts"]
        )
        if not class_check["verified"]:
            report["allowed"] = False
            report["blocks"].append(class_check["error"])

    def _check_economic_nexus(self, intent: Dict[str, Any], report: Dict[str, Any]) -> None:
        if "sales_data" not in intent or "state" not in intent:
            return
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

    def _check_trader_setoff(self, intent: Dict[str, Any], report: Dict[str, Any]) -> None:
        if "loss_head" not in intent or "offset_head" not in intent:
            return
        setoff = self.speculation.verify_setoff(
            intent["loss_head"],
            intent.get("loss_amount", 0),
            intent["offset_head"]
        )
        if not setoff["verified"]:
            report["allowed"] = False
            report["blocks"].append(setoff["error"] + " " + setoff.get("fix", ""))

    def _check_capital_gains(self, intent: Dict[str, Any], report: Dict[str, Any]) -> None:
        if "asset_type" not in intent or "dates" not in intent:
            return
        dates = intent["dates"]
        term = self.cg.determine_term(dates["buy"], dates["sell"], intent["asset_type"])
        if "claimed_rate" not in intent:
            return
        rate_check = self.cg.verify_tax_rate(intent["asset_type"], term, intent["claimed_rate"])
        if not rate_check["verified"]:
            report["allowed"] = False
            report["blocks"].append(rate_check["error"])

    def _check_corporate_loans(self, intent: Dict[str, Any], report: Dict[str, Any]) -> None:
        if "lender_type" not in intent or "borrower_role" not in intent:
            return
        loan_check = self.related_party.verify_loan_compliance(
            intent["lender_type"],
            intent["borrower_role"],
            intent.get("interest_rate", 0),
            intent.get("market_rate", 0)
        )
        if not loan_check["verified"]:
            report["allowed"] = False
            report["blocks"].append(loan_check["message"])

    def _check_startup_valuation(self, intent: Dict[str, Any], report: Dict[str, Any]) -> None:
        if "investment_round" not in intent or intent["investment_round"] != "convertible_note":
            return
        val_check = self.valuation.verify_conversion(
            intent.get("investment_amount", "0"),
            intent.get("cap_price", "0"),
            intent.get("discount", "0"),
            intent.get("next_round_price", "0")
        )
        if not val_check["verified"]:
            report["allowed"] = False
            report["blocks"].append(val_check["error"])

    def _check_international_remittance(self, intent: Dict[str, Any], report: Dict[str, Any]) -> None:
        if "remittance_amount_usd" not in intent or "purpose" not in intent:
            return
        remit_check = self.remittance.verify_lrs_limit(
            intent["remittance_amount_usd"],
            intent["purpose"],
            intent.get("fy_usage", 0)
        )
        if not remit_check["verified"]:
            report["allowed"] = False
            report["blocks"].append(remit_check["error"])

    def _check_expense_and_tds(self, intent: Dict[str, Any], report: Dict[str, Any]) -> None:
        if "expense_category" not in intent or "amount" not in intent:
            return
        # ITC Check
        itc_check = self.indirect_tax.verify_itc_eligibility(
            intent["expense_category"],
            intent.get("amount", 0),
            intent.get("tax_paid", 0)
        )
        if not itc_check["verified"]:
            report["allowed"] = False
            report["blocks"].append(itc_check["reason"])

        # TDS Check (if service type provided)
        if "service_type" not in intent:
            return
        tds_check = self.withholding.calculate_deduction(
            intent["service_type"],
            intent.get("amount", 0),
            intent.get("ytd_payment", 0)
        )
        if tds_check.get("deduction") and Decimal(tds_check["deduction"]) > 0:
            report["advisories"] = report.get("advisories", [])
            report["advisories"].append(f"TDS Required: Deduct {tds_check['deduction']} from payment.")

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

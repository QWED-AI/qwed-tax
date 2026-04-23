from typing import Any, ClassVar, Dict
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
    _ACTION_ALIASES: ClassVar[dict[str, str]] = {
        "hire_worker": "hire",
        "worker_classification": "hire",
        "sales_tax_check": "economic_nexus",
        "sales_tax_assessment": "economic_nexus",
    }

    _ACTION_CHECKS: ClassVar[dict[str, list[dict[str, Any]]]] = {
        "hire": [
            {
                "name": "worker_classification",
                "required": (
                    "worker_type",
                    "worker_facts.provides_tools",
                    "worker_facts.reimburses_expenses",
                    "worker_facts.indefinite_relationship",
                ),
                "handler": "_check_worker_classification",
            }
        ],
        "economic_nexus": [
            {
                "name": "economic_nexus",
                "required": (
                    "state",
                    "sales_data.amount",
                    "sales_data.transactions",
                    "tax_decision",
                ),
                "handler": "_check_economic_nexus",
            }
        ],
        "trade_tax": [
            {
                "name": "trader_setoff",
                "trigger": ("loss_head", "offset_head", "loss_amount"),
                "required": ("loss_head", "offset_head", "loss_amount"),
                "handler": "_check_trader_setoff",
            },
            {
                "name": "capital_gains",
                "trigger": ("asset_type", "dates", "claimed_rate"),
                "required": ("asset_type", "dates.buy", "dates.sell", "claimed_rate"),
                "handler": "_check_capital_gains",
            },
        ],
        "corporate_action": [
            {
                "name": "corporate_loans",
                "trigger": ("lender_type", "borrower_role", "interest_rate", "market_rate"),
                "required": ("lender_type", "borrower_role", "interest_rate", "market_rate"),
                "handler": "_check_corporate_loans",
            },
            {
                "name": "startup_valuation",
                "trigger": (
                    "investment_round",
                    "investment_amount",
                    "cap_price",
                    "discount",
                    "next_round_price",
                ),
                "required": (
                    "investment_round",
                    "investment_amount",
                    "cap_price",
                    "discount",
                    "next_round_price",
                ),
                "supported_if": "_supports_startup_valuation",
                "handler": "_check_startup_valuation",
            },
        ],
        "remit_money": [
            {
                "name": "international_remittance",
                "required": ("remittance_amount_usd", "purpose", "fy_usage"),
                "handler": "_check_international_remittance",
            }
        ],
        "expense_claim": [
            {
                "name": "expense_itc",
                "required": ("expense_category", "amount", "tax_paid"),
                "handler": "_check_expense_itc",
            }
        ],
        "pay_invoice": [
            {
                "name": "invoice_tds",
                "required": ("service_type", "amount", "ytd_payment"),
                "handler": "_check_invoice_tds",
            }
        ],
    }

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
            "action": "hire" | "economic_nexus" | "trade_tax" | "corporate_action" |
                      "remit_money" | "expense_claim" | "pay_invoice",
            ...
        }
        """
        if not isinstance(intent, dict) or not intent:
            return self._blocked_report(
                "TaxPreFlight requires a non-empty intent payload with an explicit action.",
                action=None,
            )

        requested_action = intent.get("action")
        canonical_action = self._normalize_action(intent.get("action"))
        if canonical_action is None:
            supported_actions = ", ".join(sorted(self._ACTION_CHECKS))
            return self._blocked_report(
                f"TaxPreFlight requires a supported action. Supported actions: {supported_actions}.",
                action=requested_action,
            )

        report = {
            "allowed": True,
            "action": canonical_action,
            "blocks": [],
            "checks_run": [],
        }

        selected_checks = self._select_checks(canonical_action, intent)
        if not selected_checks:
            report["allowed"] = False
            report["blocks"].append(self._format_missing_claim_message(canonical_action))
            return report

        for check in selected_checks:
            missing_fields = self._missing_fields(intent, check["required"])
            if missing_fields:
                report["allowed"] = False
                report["blocks"].append(
                    f"Action '{canonical_action}' is missing required fields for "
                    f"{check['name']}: {', '.join(missing_fields)}."
                )
                return report

        for check in selected_checks:
            report["checks_run"].append(check["name"])
            getattr(self, check["handler"])(intent, report)

        return report

    # ---- extracted checks (each keeps complexity flat) ----

    def _normalize_action(self, action: Any) -> str | None:
        if not isinstance(action, str) or not action.strip():
            return None
        normalized = action.strip().lower().replace(" ", "_")
        normalized = self._ACTION_ALIASES.get(normalized, normalized)
        return normalized if normalized in self._ACTION_CHECKS else None

    def _select_checks(self, action: str, intent: Dict[str, Any]) -> list[Dict[str, Any]]:
        checks = self._ACTION_CHECKS[action]
        if len(checks) == 1:
            return checks

        selected = []
        for check in checks:
            trigger_fields = check.get("trigger", check["required"])
            if not all(self._has_field(intent, field) for field in trigger_fields):
                continue

            predicate_name = check.get("supported_if")
            if predicate_name and not getattr(self, predicate_name)(intent):
                continue

            selected.append(check)
        return selected

    def _format_missing_claim_message(self, action: str) -> str:
        options = []
        for check in self._ACTION_CHECKS[action]:
            options.append(f"{check['name']} ({', '.join(check['required'])})")
        return (
            f"Action '{action}' did not include a complete verifiable claim. "
            f"Supported claim shapes: {'; '.join(options)}."
        )

    def _missing_fields(self, payload: Dict[str, Any], fields: tuple[str, ...]) -> list[str]:
        return [field for field in fields if not self._has_field(payload, field)]

    def _has_field(self, payload: Dict[str, Any], field_path: str) -> bool:
        current: Any = payload
        for part in field_path.split("."):
            if not isinstance(current, dict) or part not in current:
                return False
            current = current[part]
        return current is not None and current != ""

    def _blocked_report(self, message: str, action: Any = None) -> Dict[str, Any]:
        return {"allowed": False, "action": action, "blocks": [message], "checks_run": []}

    def _supports_startup_valuation(self, intent: Dict[str, Any]) -> bool:
        return intent.get("investment_round") == "convertible_note"

    def _check_worker_classification(self, intent: Dict[str, Any], report: Dict[str, Any]) -> None:
        class_check = self.classifier.verify_classification_claim(
            intent["worker_type"], intent["worker_facts"]
        )
        if not class_check["verified"]:
            report["allowed"] = False
            report["blocks"].append(class_check["error"])

    def _check_economic_nexus(self, intent: Dict[str, Any], report: Dict[str, Any]) -> None:
        nexus_check = self.nexus.check_nexus_liability(
            intent["state"],
            intent["sales_data"]["amount"],
            intent["sales_data"]["transactions"],
            intent["tax_decision"],
        )
        if not nexus_check["verified"]:
            report["allowed"] = False
            report["blocks"].append(nexus_check["error"])

    def _check_trader_setoff(self, intent: Dict[str, Any], report: Dict[str, Any]) -> None:
        setoff = self.speculation.verify_setoff(
            intent["loss_head"],
            intent["loss_amount"],
            intent["offset_head"]
        )
        if not setoff["verified"]:
            report["allowed"] = False
            report["blocks"].append(setoff["error"] + " " + setoff.get("fix", ""))

    def _check_capital_gains(self, intent: Dict[str, Any], report: Dict[str, Any]) -> None:
        dates = intent["dates"]
        term = self.cg.determine_term(dates["buy"], dates["sell"], intent["asset_type"])
        rate_check = self.cg.verify_tax_rate(intent["asset_type"], term, intent["claimed_rate"])
        if not rate_check["verified"]:
            report["allowed"] = False
            report["blocks"].append(rate_check.get("error", "Capital gains verification failed."))

    def _check_corporate_loans(self, intent: Dict[str, Any], report: Dict[str, Any]) -> None:
        loan_check = self.related_party.verify_loan_compliance(
            intent["lender_type"],
            intent["borrower_role"],
            intent["interest_rate"],
            intent["market_rate"]
        )
        if not loan_check["verified"]:
            report["allowed"] = False
            report["blocks"].append(loan_check["message"])

    def _check_startup_valuation(self, intent: Dict[str, Any], report: Dict[str, Any]) -> None:
        val_check = self.valuation.verify_conversion(
            intent["investment_amount"],
            intent["cap_price"],
            intent["discount"],
            intent["next_round_price"]
        )
        if not val_check["verified"]:
            report["allowed"] = False
            report["blocks"].append(val_check["error"])

    def _check_international_remittance(self, intent: Dict[str, Any], report: Dict[str, Any]) -> None:
        remit_check = self.remittance.verify_lrs_limit(
            intent["remittance_amount_usd"],
            intent["purpose"],
            intent["fy_usage"]
        )
        if not remit_check["verified"]:
            report["allowed"] = False
            report["blocks"].append(remit_check["error"])

    def _check_expense_itc(self, intent: Dict[str, Any], report: Dict[str, Any]) -> None:
        itc_check = self.indirect_tax.verify_itc_eligibility(
            intent["expense_category"],
            intent["amount"],
            intent["tax_paid"]
        )
        if not itc_check["verified"]:
            report["allowed"] = False
            report["blocks"].append(itc_check["reason"])

    def _check_invoice_tds(self, intent: Dict[str, Any], report: Dict[str, Any]) -> None:
        tds_check = self.withholding.calculate_deduction(
            intent["service_type"],
            intent["amount"],
            intent["ytd_payment"]
        )
        if not tds_check["verified"]:
            report["allowed"] = False
            report["blocks"].append(tds_check["error"])
            return

        if tds_check.get("deduction") and Decimal(tds_check["deduction"]) > 0:
            report["allowed"] = False
            report["advisories"] = report.get("advisories", [])
            report["advisories"].append(f"TDS Required: Deduct {tds_check['deduction']} from payment.")
            report["blocks"].append(
                f"Invoice payment requires TDS deduction of {tds_check['deduction']} before execution."
            )

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

from typing import Dict, Any

from qwed_tax.audit import SPECULATIVE_43_5, SPECULATIVE_SETOFF_73, build_trace
from qwed_tax.diagnostics import TaxDiagnosticResult
from qwed_tax.numeric import decimal_text, parse_decimal_input

class SpeculationGuard:
    """
    Deterministic Guard for Trading set-offs (Intraday vs F&O).
    Prevents 'Trapped Loss' errors where Speculative losses reduce Non-Speculative income.
    """

    _KNOWN_SPECULATIVE = {"intraday"}
    _KNOWN_NON_SPECULATIVE = {"f&o", "f_o", "futures", "options", "delivery", "business", "capital_gains", "capital gains"}
    _KNOWN_SOURCES = _KNOWN_SPECULATIVE | _KNOWN_NON_SPECULATIVE

    def verify_setoff(self, loss_source: str, loss_amount: Any, profit_source: str) -> Dict[str, Any]:
        """
        Deterministic Rule: Speculative losses (Intraday) cannot be set off against 
        Non-Speculative income (F&O, Delivery).
        Intraday == Speculative.
        F&O == Non-Speculative (Business).
        Delivery == Capital Gains.
        """
        # Normalize inputs
        loss_source = loss_source.lower()
        profit_source = profit_source.lower()
        try:
            parsed_loss_amount = parse_decimal_input(loss_amount, "loss_amount")
        except ValueError as exc:
            return {
                "verified": False,
                "error": str(exc),
                "fix": "Provide a finite numeric loss amount.",
                "audit_trace": build_trace(
                    SPECULATIVE_43_5, "INVALID_INPUT", {"loss_source": loss_source, "loss_amount": str(loss_amount)}
                ),
            }

        # Classify sources against known vocabulary — reject unrecognized strings
        loss_class = self._classify_source(loss_source)
        profit_class = self._classify_source(profit_source)

        if loss_class == "unknown":
            return {
                "verified": False,
                "error": f"Unrecognized loss source '{loss_source}'. Known sources: {', '.join(sorted(self._KNOWN_SOURCES))}.",
                "fix": "Use one of the recognized trading source names.",
                "audit_trace": build_trace(
                    SPECULATIVE_43_5, "UNKNOWN_LOSS_SOURCE", {"loss_source": loss_source}
                ),
            }
        if profit_class == "unknown":
            return {
                "verified": False,
                "error": f"Unrecognized profit source '{profit_source}'. Known sources: {', '.join(sorted(self._KNOWN_SOURCES))}.",
                "fix": "Use one of the recognized trading source names.",
                "audit_trace": build_trace(
                    SPECULATIVE_43_5, "UNKNOWN_PROFIT_SOURCE", {"profit_source": profit_source}
                ),
            }

        is_speculative_loss = loss_class == "speculative"
        is_speculative_profit = profit_class == "speculative"

        # STRICT RULE: Intraday Loss can ONLY be set off against Intraday Profit.
        if is_speculative_loss and not is_speculative_profit:
            return {
                "verified": False,
                "error": (
                    "Illegal Set-Off: Intraday (Speculative) loss of "
                    f"{decimal_text(parsed_loss_amount)} cannot reduce {profit_source}."
                ),
                "fix": (
                    f"Loss of {decimal_text(parsed_loss_amount)} must be CARRIED FORWARD "
                    "(4 years). It cannot be consumed now."
                ),
                "audit_trace": build_trace(
                    SPECULATIVE_SETOFF_73,
                    "ILLEGAL_SETOFF",
                    {"loss_source": loss_source, "loss_amount": decimal_text(parsed_loss_amount), "profit_source": profit_source},
                ),
            }

        return {
            "verified": True,
            "note": "Set-off allowed.",
            "audit_trace": build_trace(
                SPECULATIVE_43_5,
                "SETOFF_ALLOWED",
                {"loss_source": loss_source, "loss_amount": decimal_text(parsed_loss_amount), "profit_source": profit_source},
            ),
        }

    _UNVERIFIABLE_OUTCOMES = {"UNKNOWN_LOSS_SOURCE", "UNKNOWN_PROFIT_SOURCE"}

    @staticmethod
    def to_diagnostic(result: Dict[str, Any]) -> TaxDiagnosticResult:
        """Convert a legacy verify_setoff() dict to TaxDiagnosticResult."""
        verified = result.get("verified", False)
        audit_trace = result.get("audit_trace")

        if not verified:
            outcome = audit_trace.get("outcome") if audit_trace else None
            if outcome in SpeculationGuard._UNVERIFIABLE_OUTCOMES:
                return TaxDiagnosticResult.unverifiable(
                    agent_message="Speculative loss set-off could not be verified — unrecognized source.",
                    developer_fields={
                        "constraint_id": audit_trace["rule_id"] if audit_trace else "SPECULATIVE_UNKNOWN",
                        "audit_trace": audit_trace,
                        "error": result.get("error"),
                        "fix": result.get("fix"),
                    },
                )
            return TaxDiagnosticResult.blocked(
                agent_message="Speculative loss set-off verification could not be completed.",
                developer_fields={
                    "constraint_id": audit_trace["rule_id"] if audit_trace else "SPECULATIVE_UNKNOWN",
                    "audit_trace": audit_trace,
                    "error": result.get("error"),
                    "fix": result.get("fix"),
                },
            )

        if audit_trace is None:
            raise ValueError(
                "VERIFIED result requires audit_trace — "
                "use UNVERIFIABLE if no evidence was established."
            )

        return TaxDiagnosticResult.verified(
            agent_message="Speculative loss set-off verified.",
            developer_fields={
                "constraint_id": audit_trace["rule_id"],
                "statute": audit_trace.get("statute"),
                "jurisdiction": audit_trace.get("jurisdiction"),
                "audit_trace": audit_trace,
                "note": result.get("note"),
            },
            evidence=audit_trace,
        )

    @classmethod
    def _classify_source(cls, source: str) -> str:
        """Classify a trading source string. Returns 'speculative', 'non_speculative', or 'unknown'."""
        normalized = source.strip().lower().replace("-", "_").replace(" ", "_")
        if normalized in cls._KNOWN_SPECULATIVE:
            return "speculative"
        if normalized in cls._KNOWN_NON_SPECULATIVE:
            return "non_speculative"
        return "unknown"

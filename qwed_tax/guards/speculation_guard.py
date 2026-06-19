from typing import Dict, Any

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
            return {"verified": False, "error": str(exc), "fix": "Provide a finite numeric loss amount."}

        # Classify sources against known vocabulary — reject unrecognized strings
        loss_class = self._classify_source(loss_source)
        profit_class = self._classify_source(profit_source)

        if loss_class == "unknown":
            return {
                "verified": False,
                "error": f"Unrecognized loss source '{loss_source}'. Known sources: {', '.join(sorted(self._KNOWN_SOURCES))}.",
                "fix": "Use one of the recognized trading source names.",
            }
        if profit_class == "unknown":
            return {
                "verified": False,
                "error": f"Unrecognized profit source '{profit_source}'. Known sources: {', '.join(sorted(self._KNOWN_SOURCES))}.",
                "fix": "Use one of the recognized trading source names.",
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
            }

        return {"verified": True, "note": "Set-off allowed."}

    @classmethod
    def _classify_source(cls, source: str) -> str:
        """Classify a trading source string. Returns 'speculative', 'non_speculative', or 'unknown'."""
        for keyword in cls._KNOWN_SPECULATIVE:
            if keyword in source:
                return "speculative"
        for keyword in cls._KNOWN_NON_SPECULATIVE:
            if keyword in source:
                return "non_speculative"
        return "unknown"

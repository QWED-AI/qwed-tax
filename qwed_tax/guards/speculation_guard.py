from typing import Dict, Any

from qwed_tax.numeric import decimal_text, parse_decimal_input

class SpeculationGuard:
    """
    Deterministic Guard for Trading set-offs (Intraday vs F&O).
    Prevents 'Trapped Loss' errors where Speculative losses reduce Non-Speculative income.
    """

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
        
        is_speculative_loss = "intraday" in loss_source
        is_speculative_profit = "intraday" in profit_source
        
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

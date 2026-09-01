from decimal import Decimal
import math
from typing import Any, Dict, Optional, Union

from qwed_tax.numeric import decimal_text, parse_decimal_input

class NexusGuard:
    """
    Deterministic Guard for Economic Nexus (Sales Tax) thresholds.
    Acts as a pre-filter for Avalara/Stripe Tax.
    """
    def __init__(self):
        # 2025 Economic Nexus Thresholds (Simplified High-Risk States)
        # Source: Streamlined Sales Tax Governing Board
        self.state_thresholds = {
            "CA": {"amount": Decimal("500000"), "transactions": 0},
            "NY": {"amount": Decimal("500000"), "transactions": 100},
            "TX": {"amount": Decimal("500000"), "transactions": 0},
            "FL": {"amount": Decimal("100000"), "transactions": 0},
            "IL": {"amount": Decimal("100000"), "transactions": 200},
            "PA": {"amount": Decimal("100000"), "transactions": 0},
            "OH": {"amount": Decimal("100000"), "transactions": 200},
            "GA": {"amount": Decimal("100000"), "transactions": 200},
        }

    def check_nexus_liability(
        self,
        state: str,
        ytd_sales: Any,
        transaction_count: Union[int, float],
        llm_decision: Optional[str] = None,
        *,
        claimed_collects_tax: Optional[bool] = None,
    ) -> Dict[str, Any]:
        """
        Verify an explicit tax-collection claim against the computed nexus.

        ``llm_decision`` is retained for positional compatibility but is no
        longer interpreted: free-form model output cannot be a verification
        substrate. Callers must provide ``claimed_collects_tax`` to obtain a
        verified result; otherwise this method returns a computed-only result.
        """
        if not isinstance(state, str):
            return {
                "verified": False,
                "error": "state must be a string.",
            }
        state_code = state.upper()
        if state_code not in self.state_thresholds:
            return {
                "verified": False,
                "error": f"State {state_code} not in configured nexus threshold table. Cannot verify nexus liability — block pending rule configuration.",
            }

        try:
            parsed_sales = parse_decimal_input(ytd_sales, "ytd_sales")
        except ValueError as exc:
            return {"verified": False, "error": str(exc)}
        if parsed_sales < 0:
            return {
                "verified": False,
                "error": "ytd_sales must be a non-negative numeric value.",
            }
        # transaction_count must be a finite non-negative number — a
        # negative count is a malformed fact, not "below threshold"
        # (Sentry review on #65). Non-numeric values previously raised
        # an unhandled TypeError at the threshold comparison.
        if isinstance(transaction_count, bool) or not isinstance(transaction_count, (int, float)):
            return {
                "verified": False,
                "error": "transaction_count must be a numeric value.",
            }
        if not math.isfinite(transaction_count):
            return {
                "verified": False,
                "error": "transaction_count must be a finite numeric value.",
            }
        if transaction_count < 0:
            return {
                "verified": False,
                "error": "transaction_count must be a non-negative numeric value.",
            }
        threshold = self.state_thresholds[state_code]
        
        # Check if threshold crossed
        amount_crossed = parsed_sales >= threshold["amount"]
        tx_crossed = transaction_count >= threshold["transactions"] if threshold["transactions"] > 0 else False
        
        has_nexus = amount_crossed or tx_crossed

        reason = []
        if amount_crossed:
            reason.append(
                f"YTD Sales ${decimal_text(parsed_sales)} >= ${decimal_text(threshold['amount'])}"
            )
        if tx_crossed:
            reason.append(f"Transactions {transaction_count} >= {threshold['transactions']}")

        if claimed_collects_tax is None:
            return {
                "verified": False,
                "computed_only": True,
                "has_nexus": has_nexus,
                "error": "Computed nexus liability only. Provide claimed_collects_tax as a boolean for deterministic verification.",
            }

        if not isinstance(claimed_collects_tax, bool):
            return {
                "verified": False,
                "has_nexus": has_nexus,
                "error": "Invalid claimed_collects_tax. Expected a boolean true/false for deterministic verification.",
            }

        verified = claimed_collects_tax is has_nexus
        return {
            "verified": verified,
            "has_nexus": has_nexus,
            "claimed_collects_tax": claimed_collects_tax,
            "error": None if verified else (
                f"Nexus Violation: {state_code} threshold exceeded ({', '.join(reason)}). Tax collection is mandatory."
                if has_nexus
                else f"Nexus claim mismatch: {state_code} is below its configured threshold, but tax collection was claimed."
            ),
        }

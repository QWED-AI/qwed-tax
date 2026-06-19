from decimal import Decimal
from typing import Dict, Any

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

    def check_nexus_liability(self, state: str, ytd_sales: Any, transaction_count: int, llm_decision: str) -> Dict[str, Any]:
        """
        Verifies if the AI correctly identified that we need to pay tax in this state.
        """
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
        threshold = self.state_thresholds[state_code]
        
        # Check if threshold crossed
        amount_crossed = parsed_sales >= threshold["amount"]
        tx_crossed = transaction_count >= threshold["transactions"] if threshold["transactions"] > 0 else False
        
        has_nexus = amount_crossed or tx_crossed

        # If AI says "No Tax" but we crossed the threshold -> BLOCK
        decision_normalized = llm_decision.lower().replace(" ", "_")
        if has_nexus and (decision_normalized == "no_tax" or decision_normalized == "exempt"):
            reason = []
            if amount_crossed:
                reason.append(
                    f"YTD Sales ${decimal_text(parsed_sales)} >= ${decimal_text(threshold['amount'])}"
                )
            if tx_crossed:
                reason.append(f"Transactions {transaction_count} >= {threshold['transactions']}")
                
            return {
                "verified": False,
                "error": f"Nexus Violation: {state_code} threshold exceeded ({', '.join(reason)}). Tax collection is mandatory."
            }
            
        return {"verified": True}

from datetime import datetime
from typing import Dict, Any

class CapitalGainsGuard:
    """
    Deterministic Guard for Capital Gains Classification (STCG vs LTCG).
    Uses strict calendar logic to determine holding period.
    """
    
    def determine_term(self, purchase_date: str, sale_date: str, asset_type: str) -> str:
        """
        Calculates Holding Period in days and returns 'LTCG' or 'STCG'.
        Raises ValueError on unparseable dates or unknown asset types.
        """
        try:
            d1 = datetime.strptime(purchase_date, "%Y-%m-%d")
            d2 = datetime.strptime(sale_date, "%Y-%m-%d")
            days = (d2 - d1).days
        except (TypeError, ValueError) as exc:
            raise ValueError(
                f"Invalid date format. Expected YYYY-MM-DD, got '{purchase_date}' and '{sale_date}'."
            ) from exc

        # Deterministic Thresholds (India FY 2024-25)
        # Source: Income Tax Act
        thresholds = {
            "equity": 365,       # > 1 year
            "real_estate": 730,  # > 2 years
            "debt": 1095
        }

        if not isinstance(asset_type, str) or not asset_type.strip():
            raise ValueError(f"Unknown asset type '{asset_type}'. Known types: equity, real_estate, debt, debt_fund.")

        asset_key = asset_type.strip().lower()

        # Debt funds purchased after Apr 2023 are ALWAYS STCG (slab rate)
        # regardless of holding period — special-case before threshold lookup
        if asset_key == "debt_fund":
            return "STCG"

        if asset_key not in thresholds:
            raise ValueError(f"Unknown asset type '{asset_type}'. Known types: equity, real_estate, debt, debt_fund.")

        limit = thresholds[asset_key]
        return "LTCG" if days > limit else "STCG"

    def verify_tax_rate(self, asset_type: str, term: str, claimed_rate: str) -> Dict[str, Any]:
        """
        Verifies if the LLM hallucinated the tax rate.
        hard-coded statutory rates (FY 2024-25).
        """
        # Normalized Claims
        claimed_clean = claimed_rate.replace("%", "").strip()
        
        rates = {
            "equity_LTCG": "12.5", # Changed in Budget 2024 (was 10%)
            "equity_STCG": "20",   # Changed (was 15%)
            "debt_LTCG": "SLAB",   # Technically indexed 20% or Slab depending on purchase
            "debt_STCG": "SLAB"
        }
        
        key = f"{asset_type.lower()}_{term}"
        expected = rates.get(key)
        
        if not expected:
             return {"verified": False, "error": f"No statutory rate configured for {key}. Cannot verify claimed rate."}

        if expected == "SLAB":
            return {
                "verified": False,
                "error": (
                    f"Rate for {key} is subject to slab rates — cannot deterministically "
                    f"verify claimed rate of {claimed_rate}. Taxpayer's slab band is required for verification."
                ),
            }
            
        if claimed_clean != expected:
            return {
                "verified": False, 
                "error": f"Rate Mismatch for {key}: Statutory Rate is {expected}%, LLM claimed {claimed_rate}."
            }
            
        return {"verified": True}

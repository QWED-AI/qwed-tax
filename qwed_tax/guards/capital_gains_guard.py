from datetime import datetime
from typing import Dict, Any

from qwed_tax.audit import (
    CG_DEBT_FUND_50AA,
    CG_EQUITY_LTCG_112A,
    CG_EQUITY_STCG_111A,
    CG_NO_RATE_CONFIGURED,
    build_trace,
)
from qwed_tax.diagnostics import TaxDiagnosticResult

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
            "equity_LTCG": ("12.5", CG_EQUITY_LTCG_112A),
            "equity_STCG": ("20", CG_EQUITY_STCG_111A),
            "debt_LTCG": ("SLAB", CG_DEBT_FUND_50AA),
            "debt_STCG": ("SLAB", CG_DEBT_FUND_50AA),
        }
        
        key = f"{asset_type.lower()}_{term}"
        entry = rates.get(key)
        
        if not entry:
             return {
                 "verified": False,
                 "error": f"No statutory rate configured for {key}. Cannot verify claimed rate.",
                 "audit_trace": build_trace(
                     CG_NO_RATE_CONFIGURED, "NO_RATE", {"asset_type": asset_type, "term": term}
                 ),
             }

        expected, rule_ref = entry

        if expected == "SLAB":
            return {
                "verified": False,
                "error": (
                    f"Rate for {key} is subject to slab rates — cannot deterministically "
                    f"verify claimed rate of {claimed_rate}. Taxpayer's slab band is required for verification."
                ),
                "audit_trace": build_trace(
                    rule_ref, "SLAB_RATE", {"asset_type": asset_type, "term": term, "claimed_rate": claimed_rate}
                ),
            }
            
        if claimed_clean != expected:
            return {
                "verified": False,
                "error": f"Rate Mismatch for {key}: Statutory Rate is {expected}%, LLM claimed {claimed_rate}.",
                "audit_trace": build_trace(
                    rule_ref, "RATE_MISMATCH", {"asset_type": asset_type, "term": term, "expected": expected, "claimed": claimed_clean}
                ),
            }
            
        return {
            "verified": True,
            "audit_trace": build_trace(
                rule_ref, "RATE_VERIFIED", {"asset_type": asset_type, "term": term, "expected": expected, "claimed": claimed_clean}
            ),
        }

    _UNVERIFIABLE_OUTCOMES: frozenset[str] = frozenset({"NO_RATE", "SLAB_RATE"})

    @staticmethod
    def to_diagnostic(result: Dict[str, Any]) -> TaxDiagnosticResult:
        """Convert a legacy verify_tax_rate() dict to TaxDiagnosticResult."""
        verified = result.get("verified", False)
        audit_trace = result.get("audit_trace")

        if not verified:
            outcome = audit_trace.get("outcome") if audit_trace else None
            if outcome in CapitalGainsGuard._UNVERIFIABLE_OUTCOMES:
                return TaxDiagnosticResult.unverifiable(
                    agent_message="Capital gains tax rate could not be verified — insufficient evidence or unknown rule.",
                    developer_fields={
                        "constraint_id": audit_trace["rule_id"] if audit_trace else "CG_UNKNOWN",
                        "audit_trace": audit_trace,
                        "error": result.get("error"),
                    },
                )
            return TaxDiagnosticResult.blocked(
                agent_message="Capital gains tax rate verification could not be completed.",
                developer_fields={
                    "constraint_id": audit_trace["rule_id"] if audit_trace else "CG_UNKNOWN",
                    "audit_trace": audit_trace,
                    "error": result.get("error"),
                },
            )

        if audit_trace is None:
            raise ValueError(
                "VERIFIED result requires audit_trace — "
                "use UNVERIFIABLE if no evidence was established."
            )

        return TaxDiagnosticResult.verified(
            agent_message="Capital gains tax rate verified.",
            developer_fields={
                "constraint_id": audit_trace["rule_id"],
                "statute": audit_trace.get("statute"),
                "jurisdiction": audit_trace.get("jurisdiction"),
                "audit_trace": audit_trace,
            },
            evidence=audit_trace,
        )

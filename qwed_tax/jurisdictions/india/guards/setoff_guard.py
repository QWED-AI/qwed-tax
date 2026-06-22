from enum import Enum
from typing import Any, Dict

from qwed_tax.audit import (
    CAPITAL_GAINS_SETOFF_74,
    INTERHEAD_SETOFF_71,
    SPECULATIVE_SETOFF_73,
    build_trace,
)
from qwed_tax.diagnostics import TaxDiagnosticResult

class TaxHead(str, Enum):
    SALARY = "SALARY"
    HOUSE_PROPERTY = "HOUSE_PROPERTY"
    BUSINESS_NON_SPECULATIVE = "BUSINESS_NON_SPECULATIVE"
    BUSINESS_SPECULATIVE = "BUSINESS_SPECULATIVE" # Intraday
    CAPITAL_GAINS_LT = "CAPITAL_GAINS_LT"
    CAPITAL_GAINS_ST = "CAPITAL_GAINS_ST"
    OTHER_SOURCES = "OTHER_SOURCES"
    VDA = "VDA" # Crypto

class InterHeadAdjustmentGuard:
    """
    Verifies Inter-Head Set-off of Losses.
    Source: Audit Trace 26525cd2c6b6, 9fcb7f59948a
    """
    
    # The Matrix of Prohibitions
    # Key: The Loss Source
    # Value: List of Heads it CANNOT be set off against
    PROHIBITED_SETOFFS = {
        TaxHead.BUSINESS_SPECULATIVE: [
            TaxHead.SALARY, TaxHead.HOUSE_PROPERTY, TaxHead.BUSINESS_NON_SPECULATIVE, 
            TaxHead.CAPITAL_GAINS_LT, TaxHead.CAPITAL_GAINS_ST, TaxHead.OTHER_SOURCES
        ], # Speculative loss only against Speculative profit
        
        TaxHead.CAPITAL_GAINS_LT: [
            TaxHead.SALARY, TaxHead.HOUSE_PROPERTY, TaxHead.BUSINESS_NON_SPECULATIVE,
            TaxHead.BUSINESS_SPECULATIVE, TaxHead.OTHER_SOURCES, TaxHead.CAPITAL_GAINS_ST # LT Loss only against LT Gain
        ],
        
        TaxHead.CAPITAL_GAINS_ST: [
            TaxHead.SALARY, TaxHead.HOUSE_PROPERTY, TaxHead.BUSINESS_NON_SPECULATIVE,
            TaxHead.BUSINESS_SPECULATIVE, TaxHead.OTHER_SOURCES
        ], # ST Loss can be against ST or LT Gain (so LT is allowed, not prohibited)
        
        TaxHead.VDA: ["ALL"], # Special case: Crypto loss dead ends.

        TaxHead.SALARY: ["ALL"], # Salary losses cannot be set off against any other head.
    }

    # Heads explicitly known to have no inter-head set-off restrictions
    # (their losses can be set off against any profit head per Indian tax law)
    _EXPLICITLY_ALLOWED_LOSS_HEADS = {
        TaxHead.HOUSE_PROPERTY,
        TaxHead.BUSINESS_NON_SPECULATIVE,
        TaxHead.OTHER_SOURCES,
    }

    # Map loss heads to their RuleRef for audit_trace
    _RULE_REFS = {
        TaxHead.BUSINESS_SPECULATIVE: SPECULATIVE_SETOFF_73,
        TaxHead.CAPITAL_GAINS_LT: CAPITAL_GAINS_SETOFF_74,
        TaxHead.CAPITAL_GAINS_ST: CAPITAL_GAINS_SETOFF_74,
        TaxHead.VDA: INTERHEAD_SETOFF_71,
        TaxHead.SALARY: INTERHEAD_SETOFF_71,
        TaxHead.HOUSE_PROPERTY: INTERHEAD_SETOFF_71,
        TaxHead.BUSINESS_NON_SPECULATIVE: INTERHEAD_SETOFF_71,
        TaxHead.OTHER_SOURCES: INTERHEAD_SETOFF_71,
    }

    def verify_setoff(self, loss_head: TaxHead, profit_head: TaxHead) -> dict:
        """
        Verifies if setting off loss from 'loss_head' against profit from 'profit_head' is legal.
        """
        # 1. Check if Loss Head has restrictions
        if loss_head in self.PROHIBITED_SETOFFS:
            restrictions = self.PROHIBITED_SETOFFS[loss_head]
            rule_ref = self._RULE_REFS.get(loss_head, INTERHEAD_SETOFF_71)

            # 2. Check "ALL" condition
            if "ALL" in restrictions:
                 return {
                    "verified": False,
                    "message": f"❌ Illegal Set-Off: Loss from {loss_head.value} cannot be set off against anything (it lapses).",
                    "audit_trace": build_trace(
                        rule_ref, "ILLEGAL_SETOFF_ALL", {"loss_head": loss_head.value, "profit_head": profit_head.value}
                    ),
                }
            
            # 3. Check specific prohibition
            if profit_head in restrictions:
                 return {
                    "verified": False,
                    "message": f"❌ Illegal Set-Off: Loss from {loss_head.value} cannot be set off against {profit_head.value}.",
                    "audit_trace": build_trace(
                        rule_ref, "ILLEGAL_SETOFF", {"loss_head": loss_head.value, "profit_head": profit_head.value}
                    ),
                }

            # Loss head is in the prohibition matrix but this specific pair is not prohibited
            return {
                "verified": True,
                "message": f"✅ Allowed: {loss_head.value} loss set off against {profit_head.value}.",
                "audit_trace": build_trace(
                    rule_ref, "SETOFF_ALLOWED", {"loss_head": loss_head.value, "profit_head": profit_head.value}
                ),
            }

        # 4. Check if head is explicitly allowed (no restrictions per tax law)
        if loss_head not in self._EXPLICITLY_ALLOWED_LOSS_HEADS:
            return {
                "verified": False,
                "message": (
                    f"Loss head {loss_head.value} is not in the configured prohibition matrix "
                    "or allowlist. Cannot verify set-off legality — manual review required."
                ),
                "audit_trace": build_trace(
                    INTERHEAD_SETOFF_71, "UNKNOWN_HEAD", {"loss_head": loss_head.value, "profit_head": profit_head.value}
                ),
            }

        # If no restriction found and head is explicitly allowed, it's allowed
        rule_ref = self._RULE_REFS.get(loss_head, INTERHEAD_SETOFF_71)
        return {
            "verified": True,
            "message": f"✅ Allowed: {loss_head.value} loss set off against {profit_head.value}.",
            "audit_trace": build_trace(
                rule_ref, "SETOFF_ALLOWED", {"loss_head": loss_head.value, "profit_head": profit_head.value}
            ),
        }

    @staticmethod
    def to_diagnostic(result: Dict[str, Any]) -> TaxDiagnosticResult:
        """Convert a legacy verify_setoff() dict to TaxDiagnosticResult."""
        verified = result.get("verified", False)
        audit_trace = result.get("audit_trace")

        if not verified:
            return TaxDiagnosticResult.blocked(
                agent_message="Inter-head set-off verification could not be completed.",
                developer_fields={
                    "constraint_id": audit_trace["rule_id"] if audit_trace else "INTERHEAD_UNKNOWN",
                    "audit_trace": audit_trace,
                    "error": result.get("message"),
                },
            )

        if audit_trace is None:
            raise ValueError(
                "VERIFIED result requires audit_trace — "
                "use UNVERIFIABLE if no evidence was established."
            )

        return TaxDiagnosticResult.verified(
            agent_message="Inter-head set-off verified.",
            developer_fields={
                "constraint_id": audit_trace["rule_id"],
                "statute": audit_trace.get("statute"),
                "jurisdiction": audit_trace.get("jurisdiction"),
                "audit_trace": audit_trace,
            },
            evidence=audit_trace,
        )

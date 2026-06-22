from decimal import Decimal, ROUND_HALF_UP
from enum import Enum
from typing import Any, Dict, Optional
from pydantic import BaseModel

from qwed_tax.audit import VDA_115BBH, VDA_SETOFF_PROHIBITION, build_trace
from qwed_tax.diagnostics import TaxDiagnosticResult

class AssetClass(str, Enum):
    VDA = "VDA" # Virtual Digital Asset (Crypto/NFT)
    EQUITY = "EQUITY"
    BUSINESS = "BUSINESS"

class TaxResult(BaseModel):
    verified: bool
    message: str
    allowed_set_off: Decimal
    audit_trace: Optional[Dict[str, Any]] = None

class CryptoTaxGuard:
    """
    Verifies Section 115BBH compliance for Indian Taxation.
    Key Rule: Loss from transfer of VDA cannot be set off against any other income.
    """
    
    def verify_set_off(self, losses: Dict[str, Decimal], gains: Optional[Dict[str, Decimal]] = None) -> TaxResult:
        """
        Verifies if the proposed set-off of losses is legal.
        losses: Dict like {"VDA": -5000, "EQUITY": -200}
        gains: Optional Dict like {"BUSINESS": 10000} — reserved for future
               inter-head adjustment verification.
        """

        # Fail closed: gain-side verification is not implemented yet.
        if gains:
            return TaxResult(
                verified=False,
                message="Gain-side set-off verification is not implemented in CryptoTaxGuard. Provide losses-only payload or route to inter-head set-off guard.",
                allowed_set_off=Decimal(0),
                audit_trace=build_trace(VDA_115BBH, "GAIN_SIDE_NOT_IMPLEMENTED", {"has_gains": True}),
            )

        # Rule 1: Check for VDA Losses being used
        if "VDA" in losses and losses["VDA"] < 0:
            return TaxResult(
                verified=False,
                message="⚠️ Section 115BBH Alert: Loss from VDA (Crypto/NFT) cannot be set off against any other income. It must lapse.",
                allowed_set_off=Decimal(0),
                audit_trace=build_trace(VDA_SETOFF_PROHIBITION, "VDA_LOSS_SETOFF_BLOCKED", {"vda_loss": str(losses["VDA"])}),
            )
            
        return TaxResult(
            verified=True,
            message="✅ No restricted VDA loss set-off detected.",
            allowed_set_off=Decimal(0),
            audit_trace=build_trace(VDA_115BBH, "NO_VDA_LOSS_SETOFF", {"losses": {k: str(v) for k, v in losses.items()}}),
        )
            
    def verify_flat_tax_rate(self, vda_income: Decimal, claimed_tax: Decimal) -> TaxResult:
        """
        Verifies strict 30% tax on positive VDA income (plus cess usually, simplified here).
        """
        EXPECTED_RATE = Decimal("0.30")

        if vda_income == 0:
            if claimed_tax == 0:
                return TaxResult(
                    verified=True,
                    message="No VDA Income — zero tax confirmed.",
                    allowed_set_off=Decimal(0),
                    audit_trace=build_trace(VDA_115BBH, "ZERO_INCOME_ZERO_TAX", {"vda_income": "0", "claimed_tax": "0"}),
                )
            return TaxResult(
                verified=False,
                message=f"VDA income is zero but claimed tax is {claimed_tax}. Expected 0.",
                allowed_set_off=Decimal(0),
                audit_trace=build_trace(VDA_115BBH, "ZERO_INCOME_NONZERO_TAX", {"vda_income": "0", "claimed_tax": str(claimed_tax)}),
            )

        if vda_income < 0:
            return TaxResult(
                verified=False,
                message=f"VDA income is negative ({vda_income}) — this is a loss, not income. Use verify_set_off for loss treatment.",
                allowed_set_off=Decimal(0),
                audit_trace=build_trace(VDA_115BBH, "NEGATIVE_INCOME", {"vda_income": str(vda_income)}),
            )

        expected_tax = (vda_income * EXPECTED_RATE).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
        claimed_quantized = claimed_tax.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)

        if claimed_quantized == expected_tax:
             return TaxResult(
                verified=True,
                message=f"✅ VDA Tax correct (30% of {vda_income})",
                allowed_set_off=Decimal(0),
                audit_trace=build_trace(VDA_115BBH, "FLAT_TAX_VERIFIED", {"vda_income": str(vda_income), "expected_tax": str(expected_tax), "claimed_tax": str(claimed_tax)}),
            )
        else:
             return TaxResult(
                verified=False,
                message=f"❌ Section 115BBH Violation: VDA Income taxed at 30% flat. Expected {expected_tax}, Claimed {claimed_tax}",
                allowed_set_off=Decimal(0),
                audit_trace=build_trace(VDA_115BBH, "FLAT_TAX_MISMATCH", {"vda_income": str(vda_income), "expected_tax": str(expected_tax), "claimed_tax": str(claimed_tax)}),
            )

    _UNVERIFIABLE_OUTCOMES: frozenset[str] = frozenset({"GAIN_SIDE_NOT_IMPLEMENTED"})

    @staticmethod
    def to_diagnostic(result: TaxResult) -> TaxDiagnosticResult:
        """Convert a TaxResult to TaxDiagnosticResult."""
        verified = result.verified
        audit_trace = result.audit_trace

        if not verified:
            outcome = audit_trace.get("outcome") if audit_trace else None
            if outcome in CryptoTaxGuard._UNVERIFIABLE_OUTCOMES:
                return TaxDiagnosticResult.unverifiable(
                    agent_message="Crypto tax could not be verified — gain-side verification not implemented.",
                    developer_fields={
                        "constraint_id": audit_trace["rule_id"] if audit_trace else "VDA_UNKNOWN",
                        "audit_trace": audit_trace,
                        "error": result.message,
                        "allowed_set_off": str(result.allowed_set_off),
                    },
                )
            return TaxDiagnosticResult.blocked(
                agent_message="Crypto tax verification could not be completed.",
                developer_fields={
                    "constraint_id": audit_trace["rule_id"] if audit_trace else "VDA_UNKNOWN",
                    "audit_trace": audit_trace,
                    "error": result.message,
                    "allowed_set_off": str(result.allowed_set_off),
                },
            )

        if audit_trace is None:
            raise ValueError(
                "VERIFIED result requires audit_trace — "
                "use UNVERIFIABLE if no evidence was established."
            )

        return TaxDiagnosticResult.verified(
            agent_message="Crypto tax verified.",
            developer_fields={
                "constraint_id": audit_trace["rule_id"],
                "statute": audit_trace.get("statute"),
                "jurisdiction": audit_trace.get("jurisdiction"),
                "audit_trace": audit_trace,
                "allowed_set_off": str(result.allowed_set_off),
            },
            evidence=audit_trace,
        )

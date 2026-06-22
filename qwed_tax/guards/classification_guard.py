from enum import Enum
from typing import Dict, Any, Optional

from qwed_tax.audit import IRS_COMMON_LAW, build_trace
from qwed_tax.diagnostics import TaxDiagnosticResult

class WorkerType(Enum):
    EMPLOYEE = "W2"
    CONTRACTOR = "1099"

class ClassificationGuard:
    """
    Deterministic Guard for Worker Classification based on IRS Common Law Rules.
    Focuses on Behavioral and Financial Control.
    """
    
    def verify_worker_status(
        self,
        behavioral_control: bool,
        financial_control: bool,
        relationship_permanence: bool,
    ) -> Optional[WorkerType]:
        """
        Deterministic IRS Common Law Test.
        If an entity controls HOW work is done (behavioral) and pays expenses (financial),
        they are an Employee, not a Contractor.

        Returns:
            WorkerType.EMPLOYEE — if employee indicators are present (deterministic)
            WorkerType.CONTRACTOR — only if NO employee indicators are present
            None — if mixed signals (some but not all employee indicators)
        """
        # Count employee indicators
        employee_indicators = 0
        if behavioral_control and financial_control:
            return WorkerType.EMPLOYEE

        if relationship_permanence and behavioral_control:
            return WorkerType.EMPLOYEE

        # Track individual indicators for mixed-signal detection
        if behavioral_control:
            employee_indicators += 1
        if financial_control:
            employee_indicators += 1
        if relationship_permanence:
            employee_indicators += 1

        # Mixed signals: some employee indicators but not enough to conclusively
        # classify as employee. Must not default to contractor.
        if employee_indicators > 0:
            return None  # Ambiguous — caller must block or mark unverifiable

        # No employee indicators at all — contractor is safe
        return WorkerType.CONTRACTOR

    def verify_classification_claim(self, llm_claim: str, facts: Dict[str, Any]) -> Dict[str, Any]:
        """
        Verifies if the LLM's classification matches the deterministic facts.
        """
        derived_status = self.verify_worker_status(
            facts.get("provides_tools", False), # If employer provides tools -> Behavioral Control often implied
            facts.get("reimburses_expenses", False), # Financial Control
            facts.get("indefinite_relationship", False) # Type of Relationship
        )

        # Mixed signals — cannot conclusively classify
        if derived_status is None:
            return {
                "verified": False,
                "error": (
                    "Ambiguous classification: facts contain mixed employee/contractor indicators. "
                    "Cannot deterministically classify — manual review required."
                ),
                "audit_trace": build_trace(
                    IRS_COMMON_LAW, "AMBIGUOUS", {"facts": facts}
                ),
            }

        # Type guard — non-string claims must fail closed
        if not isinstance(llm_claim, str) or not llm_claim.strip():
            return {
                "verified": False,
                "error": "Invalid worker classification claim. Expected a non-empty string.",
                "audit_trace": build_trace(
                    IRS_COMMON_LAW, "INVALID_CLAIM", {"facts": facts}
                ),
            }

        # Normalize claim
        claim_normalized = llm_claim.upper()
        if "W-2" in claim_normalized or "EMPLOYEE" in claim_normalized:
            claim_normalized = "W2"
        elif "1099" in claim_normalized or "CONTRACTOR" in claim_normalized:
            claim_normalized = "1099"

        if derived_status.value != claim_normalized:
            return {
                "verified": False,
                "error": f"Misclassification Risk: Facts indicate {derived_status.value}, but AI claimed {llm_claim}. This creates IRS liability.",
                "audit_trace": build_trace(
                    IRS_COMMON_LAW, "MISCLASSIFICATION", {"derived": derived_status.value, "claimed": llm_claim}
                ),
            }

        return {
            "verified": True,
            "audit_trace": build_trace(
                IRS_COMMON_LAW, "CLASSIFICATION_VERIFIED", {"derived": derived_status.value, "claimed": llm_claim}
            ),
        }

    @staticmethod
    def to_diagnostic(result: Dict[str, Any]) -> TaxDiagnosticResult:
        """Convert a legacy verify_classification_claim() dict to TaxDiagnosticResult."""
        verified = result.get("verified", False)
        audit_trace = result.get("audit_trace")

        if not verified:
            return TaxDiagnosticResult.blocked(
                agent_message="Worker classification verification could not be completed.",
                developer_fields={
                    "constraint_id": audit_trace["rule_id"] if audit_trace else "IRS_COMMON_LAW_UNKNOWN",
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
            agent_message="Worker classification verified.",
            developer_fields={
                "constraint_id": audit_trace["rule_id"],
                "statute": audit_trace.get("statute"),
                "jurisdiction": audit_trace.get("jurisdiction"),
                "audit_trace": audit_trace,
            },
            evidence=audit_trace,
        )

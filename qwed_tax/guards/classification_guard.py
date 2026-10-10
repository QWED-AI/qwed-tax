import re
from enum import Enum
from typing import Dict, Any, Optional

from qwed_tax.audit import IRS_COMMON_LAW, build_trace
from qwed_tax.diagnostics import TaxDiagnosticResult

class WorkerType(Enum):
    EMPLOYEE = "W2"
    CONTRACTOR = "1099"


# Closed claim vocabulary. A claim is accepted only when, after removing
# spaces, hyphens and underscores, it equals one of these keys. Anything else
# (e.g. "non-employee", "contractor, not W-2") is an invalid claim, never a
# substring guess.
_CLAIM_ALIASES: Dict[str, WorkerType] = {
    "W2": WorkerType.EMPLOYEE,
    "EMPLOYEE": WorkerType.EMPLOYEE,
    "1099": WorkerType.CONTRACTOR,
    "1099NEC": WorkerType.CONTRACTOR,
    "CONTRACTOR": WorkerType.CONTRACTOR,
    "INDEPENDENTCONTRACTOR": WorkerType.CONTRACTOR,
}
_CLAIM_ALLOWED_CHARS = re.compile(r"[A-Za-z0-9 _-]+")
_CLAIM_SEPARATORS = re.compile(r"[ _-]+")

# Every fact must be present and a real bool: a missing fact is not evidence
# of "no employee indicator", and "no"/"false" strings are truthy.
_REQUIRED_FACTS = ("provides_tools", "reimburses_expenses", "indefinite_relationship")


def _canonical_claim(llm_claim: str) -> Optional[WorkerType]:
    """Map a claim to a WorkerType via the closed alias table, or None."""
    stripped = llm_claim.strip()
    if not _CLAIM_ALLOWED_CHARS.fullmatch(stripped):
        return None
    return _CLAIM_ALIASES.get(_CLAIM_SEPARATORS.sub("", stripped).upper())

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

    @staticmethod
    def _invalid_facts(facts: Any) -> list:
        """Return the required fact names that are missing or not bools."""
        if not isinstance(facts, dict):
            return list(_REQUIRED_FACTS)
        return [name for name in _REQUIRED_FACTS if not isinstance(facts.get(name), bool)]

    def verify_classification_claim(self, llm_claim: str, facts: Dict[str, Any]) -> Dict[str, Any]:
        """
        Verifies if the LLM's classification matches the deterministic facts.

        Fails closed (verified=False) when any required fact is missing or not
        a bool, or when the claim is not in the closed claim vocabulary.
        """
        invalid_facts = self._invalid_facts(facts)
        if invalid_facts:
            return {
                "verified": False,
                "error": (
                    "Invalid worker facts: provides_tools, reimburses_expenses and "
                    f"indefinite_relationship must all be present booleans ({', '.join(invalid_facts)})."
                ),
                "audit_trace": build_trace(
                    IRS_COMMON_LAW, "INVALID_FACTS", {"invalid_facts": invalid_facts}
                ),
            }

        derived_status = self.verify_worker_status(
            facts["provides_tools"],  # If employer provides tools -> Behavioral Control often implied
            facts["reimburses_expenses"],  # Financial Control
            facts["indefinite_relationship"],  # Type of Relationship
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

        # Map the claim through the closed vocabulary; never guess from substrings.
        claimed_status = _canonical_claim(llm_claim)
        if claimed_status is None:
            return {
                "verified": False,
                "error": (
                    "Unrecognized worker classification claim. Expected W2 / EMPLOYEE "
                    "or 1099 / 1099-NEC / CONTRACTOR / INDEPENDENT CONTRACTOR."
                ),
                "audit_trace": build_trace(
                    IRS_COMMON_LAW, "INVALID_CLAIM", {"derived": derived_status.value, "claimed": llm_claim}
                ),
            }

        if derived_status is not claimed_status:
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

    _UNVERIFIABLE_OUTCOMES: frozenset[str] = frozenset({"AMBIGUOUS"})

    @staticmethod
    def to_diagnostic(result: Dict[str, Any]) -> TaxDiagnosticResult:
        """Convert a legacy verify_classification_claim() dict to TaxDiagnosticResult."""
        verified = result.get("verified", False)
        audit_trace = result.get("audit_trace")

        if not verified:
            outcome = audit_trace.get("outcome") if audit_trace else None
            if outcome in ClassificationGuard._UNVERIFIABLE_OUTCOMES:
                return TaxDiagnosticResult.unverifiable(
                    agent_message="Worker classification could not be verified — ambiguous indicators.",
                    developer_fields={
                        "constraint_id": audit_trace["rule_id"] if audit_trace else "IRS_COMMON_LAW_UNKNOWN",
                        "audit_trace": audit_trace,
                        "error": result.get("error"),
                    },
                )
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

"""
QWED-Tax Structured Verification Diagnostics.

Implements the 3-layer TaxDiagnosticResult model (Issue #39):

    Layer 1 — Agent-Safe Diagnostics
        agent_message: str
        Agent/model-facing summary. No statute sections, no rule IDs,
        no detection logic leaked. Allows agents to correct failures
        without exposing verification internals.

    Layer 2 — Developer Diagnostics
        developer_fields: dict
        Structured developer evidence with tax-specific fields:
        constraint_id, statute, jurisdiction, expected/actual,
        advisory_checks, deduction, allowable_credit, safe_harbour_range,
        residency, net_payable, audit_trace.

    Layer 3 — Proof Diagnostics
        proof_ref: Optional[str]
        sha256 hash of retained proof artifact (audit_trace output).
        Present only when status == VERIFIED and proof was established.
        None for UNVERIFIABLE / BLOCKED — this is the authority bit.

Constraints (non-negotiable, per #39):
- Diagnostics are NOT explainability — no confidence scores, no chain-of-thought.
- All diagnostic fields must originate from verification results, constraints,
  rule evaluation, or proof systems.
- Agent-safe diagnostics must never expose detection logic, rule IDs, statute
  sections, or security bypass guidance.
- VERIFIED requires proof_ref is not None — structurally enforced.
- Non-VERIFIED rejects proof_ref — structurally enforced.
- Frozen dataclass — prevents post-construction mutation.
- Advisory checks (advisory_only=True) never set status or proof_ref.

This module does NOT depend on qwed-verification — QWED-Tax is a separate
package. The model follows the same 3-layer pattern but uses tax-specific
developer_fields and leverages the existing audit.py RuleRef + build_trace()
foundation.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional


class TaxDiagnosticStatus(str, Enum):
    """Tax verification diagnostic status.

    Three states only — no HEURISTIC, AMBIGUOUS, or CORRECTION_NEEDED.
    Richer distinctions live in developer_fields.constraint_id, not status.

    VERIFIED:
        The tax decision was deterministically proven. proof_ref MUST be present.
        Downstream gates MAY admit for control flow.

    UNVERIFIABLE:
        The tax decision could not be proven. proof_ref MUST be None.
        Reasons: insufficient evidence, ambiguous input, no claim to compare,
                 computation-only mode, unknown rule.
        Downstream gates MUST NOT admit for control flow.

    BLOCKED:
        Verification could not even be attempted. proof_ref MUST be None.
        Reasons: missing declarations, parse error, schema validation failure,
                 unsupported service/entity type, invalid input format.
        Downstream gates MUST NOT admit for control flow.
    """
    VERIFIED = "VERIFIED"
    UNVERIFIABLE = "UNVERIFIABLE"
    BLOCKED = "BLOCKED"


@dataclass(frozen=True)
class TaxAdvisoryCheck:
    """A non-proof-bearing analysis result attached as advisory metadata.

    Advisory checks may carry useful information for developers or auditors,
    but they MUST NOT influence the verification verdict. The constraint:

        advisory_only = True

    is structurally enforced: advisory checks populate
    developer_fields.advisory_checks, never status or proof_ref.
    """
    name: str
    advisory_only: bool = True
    constraint_id: Optional[str] = None
    details: Dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if self.advisory_only is not True:
            raise ValueError(
                "TaxAdvisoryCheck.advisory_only must be True — "
                "advisory checks must never influence the verification verdict."
            )

    def to_dict(self) -> Dict[str, Any]:
        return {
            "name": self.name,
            "advisory_only": self.advisory_only,
            "constraint_id": self.constraint_id,
            "details": self.details,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "TaxAdvisoryCheck":
        raw_advisory_only = data.get("advisory_only", True)
        if isinstance(raw_advisory_only, bool):
            advisory_only = raw_advisory_only
        elif isinstance(raw_advisory_only, int) and raw_advisory_only in (0, 1):
            advisory_only = bool(raw_advisory_only)
        else:
            raise ValueError(
                "TaxAdvisoryCheck.advisory_only must be a bool or integer 0/1"
            )

        return cls(
            name=data.get("name", ""),
            advisory_only=advisory_only,
            constraint_id=data.get("constraint_id"),
            details=data.get("details", {}),
        )


def compute_proof_ref(evidence: Dict[str, Any]) -> str:
    """Compute a deterministic proof reference hash from retained evidence.

    The proof_ref binds the verdict (status=VERIFIED) to the specific evidence
    that justified it. If the evidence changes, the hash changes — making
    verdict/evidence drift structurally detectable.

    For audit_trace-based guards: pass the build_trace() output as evidence.
    For Decimal guards: pass the computed + claimed values + comparison result.
    For Z3 guards: pass the assertion stack + solver result.

    Args:
        evidence: The proof artifact dict (must be JSON-serializable).

    Returns:
        sha256-prefixed hex digest string, e.g. "sha256:abcdef...".

    Raises:
        ValueError: If evidence is not JSON-serializable (fail-closed).
    """
    try:
        payload = json.dumps(evidence, sort_keys=True)
    except (TypeError, ValueError) as exc:
        raise ValueError(
            f"Proof evidence must be JSON-serializable for proof_ref hashing: {exc}"
        ) from exc
    digest = hashlib.sha256(payload.encode("utf-8")).hexdigest()
    return f"sha256:{digest}"


@dataclass(frozen=True)
class TaxDiagnosticResult:
    """Unified 3-layer tax verification diagnostic result (Issue #39).

    Replaces the ad-hoc Dict[str, Any] returns and the multiple incompatible
    result models (TaxResult, VerificationResult) across QWED-Tax guards.

    Three layers:
        1. agent_message    — Layer 1 (agent-safe, no internals)
        2. developer_fields  — Layer 2 (structured developer evidence)
        3. proof_ref         — Layer 3 (cryptographic proof artifact hash)

    Authority contract:
        proof_ref is not None  → authoritative, admissible for control flow
        proof_ref is None      → non-authoritative, NOT admissible for control flow

    Constraints enforced in __post_init__:
        - status == VERIFIED  requires proof_ref is not None
        - status == UNVERIFIABLE or BLOCKED  requires proof_ref is None
        - agent_message must be non-empty
    """

    status: TaxDiagnosticStatus
    agent_message: str
    developer_fields: Dict[str, Any] = field(default_factory=dict)
    proof_ref: Optional[str] = None

    def __post_init__(self) -> None:
        if not isinstance(self.status, TaxDiagnosticStatus):
            valid = ", ".join(s.value for s in TaxDiagnosticStatus)
            raise ValueError(f"status must be a TaxDiagnosticStatus ({valid})")

        if not isinstance(self.agent_message, str) or not self.agent_message.strip():
            raise ValueError(
                "agent_message must be a non-empty string — "
                "Layer 1 diagnostics are mandatory"
            )

        if not isinstance(self.developer_fields, dict):
            raise ValueError("developer_fields must be a dict")

        if self.status is TaxDiagnosticStatus.VERIFIED and not self.proof_ref:
            raise ValueError(
                "VERIFIED status requires proof_ref is not None and non-empty — "
                "a tax claim cannot be marked proven without a proof artifact hash. "
                "Use UNVERIFIABLE if no proof was established."
            )

        if self.status is not TaxDiagnosticStatus.VERIFIED and self.proof_ref is not None:
            raise ValueError(
                f"{self.status.value} status requires proof_ref is None — "
                "non-VERIFIED states are non-authoritative by construction."
            )

    @property
    def is_verified(self) -> bool:
        """True only when status is VERIFIED (which implies proof_ref is not None)."""
        return self.status is TaxDiagnosticStatus.VERIFIED

    @property
    def is_authoritative(self) -> bool:
        """Authority bit — True when proof_ref is present (admissible for control flow)."""
        return self.proof_ref is not None

    @property
    def is_fail_closed(self) -> bool:
        """True when status is UNVERIFIABLE or BLOCKED (non-pass, fail-closed)."""
        return self.status in (TaxDiagnosticStatus.UNVERIFIABLE, TaxDiagnosticStatus.BLOCKED)

    @property
    def constraint_id(self) -> Optional[str]:
        """The primary constraint identifier from developer_fields, if present."""
        return self.developer_fields.get("constraint_id")

    @property
    def audit_trace(self) -> Optional[Dict[str, Any]]:
        """The audit_trace from developer_fields, if present."""
        return self.developer_fields.get("audit_trace")

    @property
    def advisory_checks(self) -> List[TaxAdvisoryCheck]:
        """Advisory checks from developer_fields, deserialized to TaxAdvisoryCheck."""
        raw = self.developer_fields.get("advisory_checks", [])
        if not isinstance(raw, list):
            return []
        result = []
        for item in raw:
            if isinstance(item, dict):
                try:
                    result.append(TaxAdvisoryCheck.from_dict(item))
                except ValueError:
                    continue
            elif isinstance(item, TaxAdvisoryCheck):
                result.append(item)
        return result

    def to_dict(self) -> Dict[str, Any]:
        """Serialize to dict for API/SDK responses."""
        fields = dict(self.developer_fields)
        checks = fields.get("advisory_checks")
        if isinstance(checks, list):
            fields["advisory_checks"] = [
                item.to_dict() if isinstance(item, TaxAdvisoryCheck) else item
                for item in checks
            ]
        return {
            "status": self.status.value,
            "agent_message": self.agent_message,
            "developer_fields": fields,
            "proof_ref": self.proof_ref,
            "is_authoritative": self.is_authoritative,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "TaxDiagnosticResult":
        """Deserialize from dict."""
        status = data.get("status", "UNVERIFIABLE")
        if isinstance(status, str):
            try:
                status = TaxDiagnosticStatus(status)
            except ValueError:
                valid = ", ".join(s.value for s in TaxDiagnosticStatus)
                raise ValueError(
                    f"from_dict: invalid status {status!r} — "
                    f"must be one of: {valid}."
                ) from None
        elif not isinstance(status, TaxDiagnosticStatus):
            valid = ", ".join(s.value for s in TaxDiagnosticStatus)
            raise ValueError(
                f"from_dict: invalid status type {type(status).__name__} — "
                f"must be one of: {valid}."
            )

        agent_message = data.get("agent_message")
        if not isinstance(agent_message, str) or not agent_message.strip():
            raise ValueError(
                "from_dict: 'agent_message' is missing or empty — "
                "Layer 1 diagnostics are mandatory."
            )

        developer_fields = data.get("developer_fields", {})
        if not isinstance(developer_fields, dict):
            raise ValueError("from_dict: 'developer_fields' must be a dict.")

        return cls(
            status=status,
            agent_message=agent_message,
            developer_fields=developer_fields,
            proof_ref=data.get("proof_ref"),
        )

    @classmethod
    def verified(
        cls,
        agent_message: str,
        developer_fields: Dict[str, Any],
        evidence: Dict[str, Any],
    ) -> "TaxDiagnosticResult":
        """Construct a VERIFIED result with proof_ref computed from evidence."""
        return cls(
            status=TaxDiagnosticStatus.VERIFIED,
            agent_message=agent_message,
            developer_fields=developer_fields,
            proof_ref=compute_proof_ref(evidence),
        )

    @classmethod
    def unverifiable(
        cls,
        agent_message: str,
        developer_fields: Optional[Dict[str, Any]] = None,
    ) -> "TaxDiagnosticResult":
        """Construct an UNVERIFIABLE result (non-pass, non-authoritative)."""
        return cls(
            status=TaxDiagnosticStatus.UNVERIFIABLE,
            agent_message=agent_message,
            developer_fields=developer_fields or {},
            proof_ref=None,
        )

    @classmethod
    def blocked(
        cls,
        agent_message: str,
        developer_fields: Optional[Dict[str, Any]] = None,
    ) -> "TaxDiagnosticResult":
        """Construct a BLOCKED result (verification could not be attempted)."""
        return cls(
            status=TaxDiagnosticStatus.BLOCKED,
            agent_message=agent_message,
            developer_fields=developer_fields or {},
            proof_ref=None,
        )


__all__ = [
    "TaxDiagnosticStatus",
    "TaxDiagnosticResult",
    "TaxAdvisoryCheck",
    "compute_proof_ref",
]

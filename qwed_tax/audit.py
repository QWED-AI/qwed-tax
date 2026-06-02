"""
Structured statutory audit trace for guard verdicts.

Guards historically return free-text ``reason`` / ``error`` strings. That is
fine for humans but not machine-readable: an auditor cannot reliably answer
"which statute drove this block?" by parsing prose.

This module provides a small, shared, additive structure that guards can attach
to their results under the ``audit_trace`` key. Existing keys are never changed,
so callers that ignore ``audit_trace`` keep working unchanged.

Rule identifiers and statute strings live here as constants so that multiple
guards (and future ones) reference the same canonical values instead of
duplicating inline literals.
"""

from __future__ import annotations

import copy
from dataclasses import dataclass
from typing import Any, Dict, Optional

JURISDICTION_INDIA = "INDIA"


@dataclass(frozen=True)
class RuleRef:
    """A canonical, immutable (rule_id, statute, jurisdiction) reference."""

    rule_id: str
    statute: str
    jurisdiction: str = JURISDICTION_INDIA


# --- Centralised rule references -------------------------------------------
# Input Tax Credit (GST)
ITC_BLOCKED_17_5 = RuleRef("ITC_BLOCKED_17_5", "CGST Act, Section 17(5)")
ITC_PERSONAL_CONSUMPTION = RuleRef(
    "ITC_PERSONAL_CONSUMPTION", "CGST Act, Section 17(5)(g)"
)
ITC_ELIGIBLE = RuleRef("ITC_ELIGIBLE", "CGST Act, Section 16")
ITC_GIFT_THRESHOLD = RuleRef("ITC_GIFT_THRESHOLD", "CGST Act, Section 17(5)(h)")


# Tax Deducted at Source (Income Tax Act)
TDS_194J = RuleRef("TDS_194J", "Income Tax Act, Section 194J")
TDS_194C = RuleRef("TDS_194C", "Income Tax Act, Section 194C")
TDS_194H = RuleRef("TDS_194H", "Income Tax Act, Section 194H")
TDS_194I = RuleRef("TDS_194I", "Income Tax Act, Section 194I")


def build_trace(
    rule: RuleRef,
    outcome: str,
    inputs: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """
    Build a structured audit-trace entry for a guard verdict.

    Args:
        rule: the canonical rule reference that drove the verdict.
        outcome: short machine-readable outcome, e.g. "BLOCKED", "ALLOWED",
            "DEDUCTION_REQUIRED".
        inputs: the decision-relevant inputs (already normalised), so the
            verdict can be reproduced/audited.

    Returns:
        A plain dict suitable for embedding under a result's ``audit_trace`` key.
    """
    return {
        "rule_id": rule.rule_id,
        "statute": rule.statute,
        "jurisdiction": rule.jurisdiction,
        "outcome": outcome,
        "inputs": copy.deepcopy(inputs) if inputs else {},
    }

"""Regression tests: ClassificationGuard claim vocabulary and fact typing.

A claim must map through a closed vocabulary (never a substring match), and
all three worker facts must be present booleans. Anything else fails closed.
"""
import pytest

from qwed_tax import TaxPreFlight
from qwed_tax.diagnostics import TaxDiagnosticStatus
from qwed_tax.guards.classification_guard import ClassificationGuard

EMPLOYEE_FACTS = {"provides_tools": True, "reimburses_expenses": True, "indefinite_relationship": True}
CONTRACTOR_FACTS = {"provides_tools": False, "reimburses_expenses": False, "indefinite_relationship": False}


@pytest.fixture
def guard():
    return ClassificationGuard()


@pytest.mark.parametrize("claim", [
    "1099 non-employee contractor",
    "Non-Employee Compensation (1099-NEC)",
    "Independent contractor (not an employee)",
    "1099 (paid as non-employee)",
    "contractor, not W-2",
    "W-2 or 1099",
    "self-employed 1099",
    "employee?",
])
def test_free_text_claims_are_rejected(guard, claim):
    for facts in (EMPLOYEE_FACTS, CONTRACTOR_FACTS):
        res = guard.verify_classification_claim(claim, facts)
        assert res["verified"] is False
        assert res["audit_trace"]["outcome"] == "INVALID_CLAIM"
        diag = ClassificationGuard.to_diagnostic(res)
        assert diag.status is not TaxDiagnosticStatus.VERIFIED
        assert diag.proof_ref is None


@pytest.mark.parametrize("claim", ["W2", "w2", "W-2", " w-2 ", "W_2", "Employee", "EMPLOYEE"])
def test_employee_aliases_match_employee_facts(guard, claim):
    assert guard.verify_classification_claim(claim, EMPLOYEE_FACTS)["verified"] is True
    res = guard.verify_classification_claim(claim, CONTRACTOR_FACTS)
    assert res["verified"] is False
    assert res["audit_trace"]["outcome"] == "MISCLASSIFICATION"


@pytest.mark.parametrize("claim", ["1099", "1099-NEC", "1099 nec", "Contractor", "independent contractor", "Independent-Contractor"])
def test_contractor_aliases_match_contractor_facts(guard, claim):
    assert guard.verify_classification_claim(claim, CONTRACTOR_FACTS)["verified"] is True
    res = guard.verify_classification_claim(claim, EMPLOYEE_FACTS)
    assert res["verified"] is False
    assert res["audit_trace"]["outcome"] == "MISCLASSIFICATION"


@pytest.mark.parametrize("facts", [
    {},
    {"provides_tools": True, "reimburses_expenses": True},
    {"provides_tools": "no", "reimburses_expenses": "no", "indefinite_relationship": "no"},
    {"provides_tools": "false", "reimburses_expenses": False, "indefinite_relationship": False},
    {"provides_tools": 0, "reimburses_expenses": 0, "indefinite_relationship": 0},
    {"provides_tools": None, "reimburses_expenses": False, "indefinite_relationship": False},
    None,
    ["provides_tools"],
])
def test_missing_or_non_bool_facts_fail_closed(guard, facts):
    for claim in ("1099", "W2"):
        res = guard.verify_classification_claim(claim, facts)
        assert res["verified"] is False
        assert res["audit_trace"]["outcome"] == "INVALID_FACTS"
        diag = ClassificationGuard.to_diagnostic(res)
        assert diag.status is TaxDiagnosticStatus.BLOCKED
        assert diag.proof_ref is None


def test_invalid_facts_names_the_bad_fields(guard):
    res = guard.verify_classification_claim("1099", {"provides_tools": False, "reimburses_expenses": "no"})
    assert res["audit_trace"]["inputs"]["invalid_facts"] == ["reimburses_expenses", "indefinite_relationship"]


def test_preflight_hire_rejects_free_text_contractor_claim():
    report = TaxPreFlight().audit_transaction({
        "action": "hire",
        "worker_type": "1099 non-employee contractor",
        "worker_facts": EMPLOYEE_FACTS,
    })
    assert report["allowed"] is False
    assert report["checks_run"] == ["worker_classification"]


def test_preflight_hire_rejects_string_facts():
    report = TaxPreFlight().audit_transaction({
        "action": "hire",
        "worker_type": "W-2",
        "worker_facts": {"provides_tools": "no", "reimburses_expenses": "no", "indefinite_relationship": "no"},
    })
    assert report["allowed"] is False
    assert "booleans" in report["blocks"][0]


def test_preflight_hire_valid_claims_unchanged():
    pf = TaxPreFlight()
    ok = pf.audit_transaction({"action": "hire", "worker_type": "W2", "worker_facts": EMPLOYEE_FACTS})
    assert ok["allowed"] is True
    blocked = pf.audit_transaction({"action": "hire", "worker_type": "1099", "worker_facts": EMPLOYEE_FACTS})
    assert blocked["allowed"] is False
    assert "Misclassification Risk" in blocked["blocks"][0]

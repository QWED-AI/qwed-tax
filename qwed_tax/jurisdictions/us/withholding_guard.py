from decimal import Decimal
from typing import Any, Dict

from z3 import Solver, Bool, Real, RealVal, Implies, And, sat
from pydantic import BaseModel, field_validator

from qwed_tax.audit import W4_EXEMPT_PUB505, build_trace
from qwed_tax.diagnostics import TaxDiagnosticResult
from qwed_tax.numeric import parse_decimal_input

class W4Form(BaseModel):
    employee_id: str
    claim_exempt: bool
    tax_liability_last_year: Decimal
    expect_refund_this_year: bool

    @field_validator("tax_liability_last_year", mode="before")
    @classmethod
    def validate_tax_liability_last_year(cls, value):
        return parse_decimal_input(value, "tax_liability_last_year")

class WithholdingGuard:
    """
    Verifies W-4 Withholding Compliance using Z3 Theorem Prover.
    """
    
    def verify_exempt_status(self, form: W4Form) -> Dict[str, Any]:
        """
        Verifies if an employee is legally allowed to claim 'Exempt' status.
        Rule: To claim exempt, you must have had no tax liability last year 
              AND expect to have no tax liability this year.
        """
        s = Solver()
        
        # Define Z3 Variables
        exempt = Bool('claim_exempt')
        liability_last = Real('liability_last_year')
        expect_no_liability = Bool('expect_refund_this_year') # True means they expect refund/no tax
        
        # 1. The Divine Rule (IRS Pub 505)
        # If Exempt is True, THEN (LiabilityLast == 0 AND ExpectNoLiability == True)
        # We assert the Rule must always be true for a VALID form.
        # But here, we want to check if THIS SPECIFIC FORM is valid under the rule.
        
        # So we add the Rule to the solver.
        rule = Implies(exempt, And(liability_last == 0, expect_no_liability))
        s.add(rule)
        
        # 2. Add the User's Input as constraints
        s.add(exempt == form.claim_exempt)
        s.add(liability_last == RealVal(str(form.tax_liability_last_year)))
        s.add(expect_no_liability == form.expect_refund_this_year)
        
        # 3. Check consistency
        # If UNSAT, it means the User's Input contradicts the Rule.
        result = s.check()
        
        if result == sat:
            return {
                "verified": True,
                "message": "✅ W-4 Form represents a valid combination.",
                "audit_trace": build_trace(W4_EXEMPT_PUB505, "EXEMPT_VALID", {"employee_id": form.employee_id, "claim_exempt": form.claim_exempt, "tax_liability_last_year": str(form.tax_liability_last_year), "expect_refund_this_year": form.expect_refund_this_year}),
            }
        else:
            return {
                "verified": False,
                "message": "❌ IRS VIOLATION: Cannot claim 'Exempt' if you had tax liability last year or expect it this year.",
                "audit_trace": build_trace(W4_EXEMPT_PUB505, "EXEMPT_VIOLATION", {"employee_id": form.employee_id, "claim_exempt": form.claim_exempt, "tax_liability_last_year": str(form.tax_liability_last_year), "expect_refund_this_year": form.expect_refund_this_year}),
            }

    @staticmethod
    def to_diagnostic(result: Dict[str, Any]) -> TaxDiagnosticResult:
        """Convert a legacy verify_exempt_status() dict to TaxDiagnosticResult."""
        verified = result.get("verified", False)
        audit_trace = result.get("audit_trace")

        if not verified:
            return TaxDiagnosticResult.blocked(
                agent_message="W-4 exempt status verification could not be completed.",
                developer_fields={
                    "constraint_id": audit_trace["rule_id"] if audit_trace else "W4_UNKNOWN",
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
            agent_message="W-4 exempt status verified.",
            developer_fields={
                "constraint_id": audit_trace["rule_id"],
                "statute": audit_trace.get("statute"),
                "jurisdiction": audit_trace.get("jurisdiction"),
                "audit_trace": audit_trace,
            },
            evidence=audit_trace,
        )

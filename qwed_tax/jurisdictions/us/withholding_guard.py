from z3 import *
from pydantic import BaseModel

class W4Form(BaseModel):
    employee_id: str
    claim_exempt: bool
    tax_liability_last_year: float # Using float for Z3 compatibility (representing currency)
    expect_refund_this_year: bool

class WithholdingGuard:
    """
    Verifies W-4 Withholding Compliance using Z3 Theorem Prover.
    """
    
    def verify_exempt_status(self, form: W4Form):
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
        s.add(liability_last == form.tax_liability_last_year)
        s.add(expect_no_liability == form.expect_refund_this_year)
        
        # 3. Check consistency
        # If UNSAT, it means the User's Input contradicts the Rule.
        result = s.check()
        
        if result == sat:
            return {"verified": True, "message": "✅ W-4 Form represents a valid combination."}
        else:
            # We can find the core contradiction if needed, but for now simple return
            return {
                "verified": False, 
                "message": "❌ IRS VIOLATION: Cannot claim 'Exempt' if you had tax liability last year or expect it this year."
            }

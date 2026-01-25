from z3 import *
from .models import WorkerClassificationParams, State

class ClassificationGuard:
    """
    Verifies Worker Classification (Employee vs Independent Contractor).
    Implements the 'ABC Test' used in CA (AB5), MA, NJ.
    
    Logic: 
    Contractor IF (A=True AND B=True AND C=True).
    Otherwise: Employee.
    """
    
    def verify_classification(self, params: WorkerClassificationParams, claimed_status_contractor: bool) -> dict:
        """
        Verifies if the claimed status matches the legal reality defined by inputs.
        params: The facts of the relationship (Control, Business Scope, Independence).
        claimed_status_contractor: What the user/LLM thinks usage is (True=1099, False=W2).
        """
        s = Solver()
        
        # Z3 Variables
        is_contractor = Bool('is_contractor')
        
        # Criteria
        A_control_free = Bool('A_freedom_from_control')
        B_outside_business = Bool('B_work_outside_usual_business')
        C_independent_trade = Bool('C_customarily_engaged_independently')
        
        # The ABC Rule (Strict Conjunction)
        # To be a contractor, ALL three must be true.
        abc_rule = (is_contractor == And(A_control_free, B_outside_business, C_independent_trade))
        s.add(abc_rule)
        
        # Add Facs from Input
        s.add(A_control_free == params.freedom_from_control)
        s.add(B_outside_business == params.work_outside_usual_business)
        s.add(C_independent_trade == params.customarily_engaged_independently)
        
        # Add the Claim to check consistency
        # We want to check if Claim == Reality
        s.add(is_contractor == claimed_status_contractor)
        
        result = s.check()
        
        if result == sat:
            return {
                "verified": True,
                "classification": "Contractor (1099)" if claimed_status_contractor else "Employee (W-2)",
                "message": "✅ Classification is improved by ABC test logic."
            }
        else:
            # Contradiction found.
            # Determine the correct status
            s.reset()
            s.add(abc_rule)
            s.add(A_control_free == params.freedom_from_control)
            s.add(B_outside_business == params.work_outside_usual_business)
            s.add(C_independent_trade == params.customarily_engaged_independently)
            
            # Check what it SHOULD be
            s.check()
            m = s.model()
            correct_is_contractor = is_true(m[is_contractor])
            
            legal_status = "Independent Contractor (1099)" if correct_is_contractor else "Employee (W-2)"
            
            reasons = []
            if not params.freedom_from_control: reasons.append("Failed A (Under Control)")
            if not params.work_outside_usual_business: reasons.append("Failed B (Core Business Work)")
            if not params.customarily_engaged_independently: reasons.append("Failed C (No Independent Business)")
            
            return {
                "verified": False,
                "classification": legal_status,
                "message": f"❌ MISCLASSIFICATION: Laws in {params.state.value} require {legal_status}. Reasons: {', '.join(reasons)}"
            }

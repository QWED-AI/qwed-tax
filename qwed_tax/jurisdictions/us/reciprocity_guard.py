from z3 import *
from ...models import WorkArrangement, State

class ReciprocityGuard:
    """
    Verifies State Income Tax Reciprocity Agreements.
    Example: NJ residents working in PA do NOT pay PA tax, they pay NJ tax.
    """
    
    def __init__(self):
        # We model agreements as pairs of states (Residence, Work)
        # If (R, W) is in standard_reciprocity, then you pay tax in R, not W.
        self.reciprocal_pairs = {
            (State.NJ, State.PA), (State.PA, State.NJ),
            (State.MD, State.PA), (State.PA, State.MD),
            (State.VA, State.MD), (State.MD, State.VA), # DC area
        }

    def determine_withholding_state(self, arrangement: WorkArrangement) -> dict:
        """
        Uses Z3 to prove which state should receive withholding.
        """
        s = Solver()
        
        # Z3 Variables representing State Enums as Integers could be complex,
        # but for this logic, we use Booleans for "IsReciprocal".
        
        residence = arrangement.residence_address.state
        work = arrangement.work_address.state
        
        # 1. Proposition: Reciprocity Exists
        # Ideally we'd encode the whole table in Z3, but for hybrid approach:
        reciprocity_exists_val = (residence, work) in self.reciprocal_pairs
        
        reciprocity_active = Bool('reciprocity_active')
        same_state = Bool('same_state')
        pay_residence = Bool('pay_residence_state')
        
        # 2. Logic Rules
        # Rule 1: Identity. If you live and work in same state, pay that state.
        s.add(Implies(same_state, pay_residence))
        
        # Rule 2: Reciprocity. If Diff State AND Reciprocity Agreements, pay Residence.
        s.add(Implies(And(Not(same_state), reciprocity_active), pay_residence))
        
        # Rule 3: No Reciprocity. If Diff State AND No Reciprocity, pay Work State (usually).
        # (Simplified rule - creates nexus).
        s.add(Implies(And(Not(same_state), Not(reciprocity_active)), Not(pay_residence)))
        
        # 3. Add Facts
        s.add(same_state == (residence == work))
        s.add(reciprocity_active == reciprocity_exists_val)
        
        # 4. Check
        result = s.check()
        
        if result == sat:
            m = s.model()
            should_pay_residence = is_true(m[pay_residence])
            
            target_state = residence if should_pay_residence else work
            
            reason = ""
            if same_state == True or residence == work:
                reason = "Employees living and working in same state pay that state tax."
            elif should_pay_residence:
                reason = f"Reciprocity Agreement exists between {residence} and {work}. Withhold for Residence ({residence})."
            else:
                reason = f"No Reciprocity between {residence} and {work}. Withhold for Work State ({work})."
                
            return {
                "verified": True,
                "withholding_state": target_state,
                "reason": reason
            }
        else:
            return {"verified": False, "message": "Logic Error in Tax Rules"}

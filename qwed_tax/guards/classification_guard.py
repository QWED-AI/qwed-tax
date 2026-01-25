from enum import Enum
from typing import Dict, Any

class WorkerType(Enum):
    EMPLOYEE = "W2"
    CONTRACTOR = "1099"

class ClassificationGuard:
    """
    Deterministic Guard for Worker Classification based on IRS Common Law Rules.
    Focuses on Behavioral and Financial Control.
    """
    
    def verify_worker_status(self, behavioral_control: bool, financial_control: bool, relationship_permanence: bool) -> WorkerType:
        """
        Deterministic IRS Common Law Test.
        If an entity controls HOW work is done (behavioral) and pays expenses (financial),
        they are an Employee, not a Contractor.
        """
        # Strict rule: If you control behavior and finances, it's an employee.
        if behavioral_control and financial_control:
            return WorkerType.EMPLOYEE
            
        # If the relationship is permanent (indefinite), likely an employee unless completely independent
        if relationship_permanence and behavioral_control:
             return WorkerType.EMPLOYEE
        
        # Default to Contractor only if significant control is absent
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
        
        # Normalize claim
        claim_normalized = llm_claim.upper()
        if "W-2" in claim_normalized or "EMPLOYEE" in claim_normalized:
            claim_normalized = "W2"
        elif "1099" in claim_normalized or "CONTRACTOR" in claim_normalized:
            claim_normalized = "1099"
            
        if derived_status.value != claim_normalized:
            return {
                "verified": False,
                "error": f"Misclassification Risk: Facts indicate {derived_status.value}, but AI claimed {llm_claim}. This creates IRS liability."
            }
        return {"verified": True}

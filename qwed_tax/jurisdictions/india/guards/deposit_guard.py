from decimal import Decimal
from pydantic import BaseModel

class RateCheckResult(BaseModel):
    verified: bool
    expected_rate: Decimal
    claimed_rate: Decimal
    message: str

class DepositRateGuard:
    """
    Verifies Bank Deposit Rates, specifically Senior Citizen premiums.
    Source: Audit Trace 50ebf9bc8d10
    """
    
    def verify_fd_rate(self, age: int, base_rate: Decimal, claimed_rate: Decimal, senior_premium: Decimal = Decimal("0.50")) -> RateCheckResult:
        """
        Verifies if the interest rate includes the correct age-based premium.
        """
        expected_rate = base_rate
        
        # Rule: Senior Citizens (60+) get extra interest
        is_senior = age >= 60
        if is_senior:
            expected_rate += senior_premium
            
        # We check for exact match because rates are strict policy
        if claimed_rate == expected_rate:
            return RateCheckResult(
                verified=True,
                expected_rate=expected_rate,
                claimed_rate=claimed_rate,
                message=f"✅ Rate Verified (Age {age}: Base {base_rate}% + Premium {senior_premium if is_senior else 0}%)"
            )
        else:
            return RateCheckResult(
                verified=False,
                expected_rate=expected_rate,
                claimed_rate=claimed_rate,
                message=f"❌ Rate Error: Age {age} should get {expected_rate}%, but LLM claimed {claimed_rate}%."
            )

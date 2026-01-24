from pydantic import BaseModel, Field, field_validator
from decimal import Decimal
from typing import List, Optional
from enum import Enum

class Currency(str, Enum):
    USD = "USD"
    EUR = "EUR"
    GBP = "GBP"

class DeductionType(str, Enum):
    PRE_TAX = "PRE_TAX"   # 401k, Health Insurance
    POST_TAX = "POST_TAX" # Roth 401k, Garnishments

class TaxEntry(BaseModel):
    name: str # e.g. "Federal Income Tax", "Social Security"
    amount: Decimal
    
class DeductionEntry(BaseModel):
    name: str
    amount: Decimal
    type: DeductionType

class PayrollEntry(BaseModel):
    employee_id: str
    gross_pay: Decimal
    taxes: List[TaxEntry]
    deductions: List[DeductionEntry]
    net_pay_claimed: Decimal # What the LLM/System calculated
    currency: Currency = Currency.USD

class VerificationResult(BaseModel):
    verified: bool
    recalculated_net_pay: Decimal
    discrepancy: Decimal
    message: str

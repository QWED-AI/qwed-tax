from pydantic import BaseModel, Field, field_validator
from decimal import Decimal
from typing import List, Optional, Literal
from enum import Enum

class Currency(str, Enum):
    USD = "USD"
    EUR = "EUR"
    GBP = "GBP"

class DeductionType(str, Enum):
    PRE_TAX = "PRE_TAX"   # 401k, Health Insurance
    POST_TAX = "POST_TAX" # Roth 401k, Garnishments

class State(str, Enum):
    # Simplified list for demo
    NY = "NY"
    NJ = "NJ"
    CA = "CA"
    TX = "TX"
    PA = "PA"
    FL = "FL"
    MD = "MD"
    VA = "VA"

class Address(BaseModel):
    street: str
    city: str
    state: State
    zip_code: str

class WorkArrangement(BaseModel):
    employee_id: str
    residence_address: Address
    work_address: Address
    # If remote, work_address might be same as residence or HQ
    is_remote: bool = False

class PaymentType(str, Enum):
    NON_EMPLOYEE_COMPENSATION = "NEC" # Services
    RENT = "RENT"
    ROYALTIES = "ROYALTIES"
    ATTORNEY_FEES = "ATTORNEY"
    HEALTHCARE = "HEALTHCARE"

class ContractorPayment(BaseModel):
    contractor_id: str
    payment_type: PaymentType
    amount: Decimal
    calendar_year: int 

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

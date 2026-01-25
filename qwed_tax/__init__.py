__version__ = "0.2.0"

from .models import (
    PayrollEntry, TaxEntry, DeductionEntry, DeductionType, 
    Currency, State, Address, WorkArrangement,
    ContractorPayment, PaymentType, WorkerClassificationParams
)

# US Guards
from .jurisdictions.us.payroll_guard import PayrollGuard
from .jurisdictions.us.withholding_guard import WithholdingGuard, W4Form
from .jurisdictions.us.reciprocity_guard import ReciprocityGuard
from .jurisdictions.us.form1099_guard import Form1099Guard
from .jurisdictions.us.classification_guard import ClassificationGuard

# India Guards
from .jurisdictions.india.guards.crypto_guard import CryptoTaxGuard
from .jurisdictions.india.guards.investment_guard import InvestmentGuard
from .jurisdictions.india.guards.gst_guard import GSTGuard

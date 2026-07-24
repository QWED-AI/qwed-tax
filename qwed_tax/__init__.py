__version__ = "0.2.0"

from .models import (
    PayrollEntry,
    TaxEntry,
    DeductionEntry,
    DeductionType,
    Currency,
    State,
    Address,
    WorkArrangement,
    ContractorPayment,
    PaymentType,
    WorkerClassificationParams,
    VerificationResult,
)

# Diagnostics (v0.2.0)
from .diagnostics import (
    TaxDiagnosticResult,
    TaxDiagnosticStatus,
    TaxAdvisoryCheck,
    compute_proof_ref,
)

# Main entry points
from .verifier import TaxPreFlight, TaxVerifier

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
from .jurisdictions.india.guards.deposit_guard import DepositRateGuard
from .jurisdictions.india.guards.setoff_guard import InterHeadAdjustmentGuard, TaxHead

# Domain Guards
from .guards.tds_guard import TDSGuard
from .guards.indirect_tax_guard import InputCreditGuard
from .guards.remittance_guard import RemittanceGuard
from .guards.nexus_guard import NexusGuard
from .guards.capital_gains_guard import CapitalGainsGuard
from .guards.speculation_guard import SpeculationGuard
from .guards.related_party_guard import RelatedPartyGuard
from .guards.valuation_guard import ValuationGuard
from .guards.dtaa_guard import DTAAGuard
from .guards.transfer_pricing_guard import TransferPricingGuard
from .guards.poem_guard import PoEMGuard
from .address_guard import AddressGuard

# Middleware
from .middleware.gusto_interceptor import QWEDTaxMiddleware

__all__ = [  # noqa: RUF022
    "__version__",
    # Models
    "PayrollEntry",
    "TaxEntry",
    "DeductionEntry",
    "DeductionType",
    "Currency",
    "State",
    "Address",
    "WorkArrangement",
    "ContractorPayment",
    "PaymentType",
    "WorkerClassificationParams",
    "VerificationResult",
    # Diagnostics
    "TaxDiagnosticResult",
    "TaxDiagnosticStatus",
    "TaxAdvisoryCheck",
    "compute_proof_ref",
    # Entry points
    "TaxPreFlight",
    "TaxVerifier",
    # US
    "PayrollGuard",
    "WithholdingGuard",
    "W4Form",
    "ReciprocityGuard",
    "Form1099Guard",
    "ClassificationGuard",
    # India
    "CryptoTaxGuard",
    "InvestmentGuard",
    "GSTGuard",
    "DepositRateGuard",
    "InterHeadAdjustmentGuard",
    "TaxHead",
    # Domain
    "TDSGuard",
    "InputCreditGuard",
    "RemittanceGuard",
    "NexusGuard",
    "CapitalGainsGuard",
    "SpeculationGuard",
    "RelatedPartyGuard",
    "ValuationGuard",
    "DTAAGuard",
    "TransferPricingGuard",
    "PoEMGuard",
    "AddressGuard",
    # Middleware
    "QWEDTaxMiddleware",
]

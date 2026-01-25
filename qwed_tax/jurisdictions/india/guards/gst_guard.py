from enum import Enum
from pydantic import BaseModel

class EntityType(str, Enum):
    INDIVIDUAL = "INDIVIDUAL"
    BODY_CORPORATE = "BODY_CORPORATE" # Company/LLP
    PARTNERSHIP = "PARTNERSHIP"
    GOVERNMENT = "GOVERNMENT"

class ServiceType(str, Enum):
    GTA = "GTA" # Goods Transport Agency
    LEGAL = "LEGAL" # Advocates
    SECURITY = "SECURITY"
    RENTING_VEHICLE = "RENTING_VEHICLE"
    OTHER = "OTHER"

class GSTGuard:
    """
    Verifies GST Liability: Forward Charge (FCM) vs Reverse Charge (RCM).
    Source: Audit Trace d60764a02d73
    """
    
    def verify_rcm_applicability(self, service: ServiceType, provider: EntityType, recipient: EntityType) -> dict:
        """
        Determines who is liable to pay tax.
        """
        # Deterministic RCM Rules (Simplified for demo)
        
        is_rcm = False
        reason = "Forward Charge (Provider pays)"
        
        # Rule: GTA Service provided to Body Corporate -> RCM
        if service == ServiceType.GTA:
            if recipient in [EntityType.BODY_CORPORATE, EntityType.PARTNERSHIP]:
                is_rcm = True
                reason = "GTA service received by Body Corporate/Partnership attracts RCM."
        
        # Rule: Legal Service provided to Business -> RCM
        elif service == ServiceType.LEGAL:
            if recipient == EntityType.BODY_CORPORATE:
                is_rcm = True
                reason = "Legal service to Business Entity attracts RCM."

        # Rule: Security Services provided by Non-Body Corporate to Registered Person -> RCM
        elif service == ServiceType.SECURITY:
            if provider != EntityType.BODY_CORPORATE and recipient == EntityType.BODY_CORPORATE:
               is_rcm = True
               reason = "Security by Non-Body Corporate attracts RCM."

        return {
            "verified": True,
            "liability": "RECIPIENT (RCM)" if is_rcm else "PROVIDER (FCM)",
            "is_rcm": is_rcm,
            "reason": reason
        }

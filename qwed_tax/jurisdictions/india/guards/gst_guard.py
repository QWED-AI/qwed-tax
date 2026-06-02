from enum import Enum
from typing import Any, Dict
from decimal import Decimal

from pydantic import BaseModel

from qwed_tax.numeric import decimal_text, parse_decimal_input

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

    # Two paise of tolerance absorbs benign half-rate rounding on the CGST/SGST
    # legs without letting a materially wrong split slip through.
    _SPLIT_TOLERANCE = Decimal("0.02")

    def verify_gst_split(
        self,
        supplier_state: str,
        place_of_supply: str,
        taxable_value: Any,
        gst_rate: Any,
        claimed_cgst: Any,
        claimed_sgst: Any,
        claimed_igst: Any,
    ) -> Dict[str, Any]:
        """
        Verify that a claimed CGST/SGST/IGST breakup matches the supply type.

        Place-of-supply rule:
          - Intra-state (supplier_state == place_of_supply):
                CGST = SGST = taxable_value * rate / 2, and IGST must be 0.
          - Inter-state (supplier_state != place_of_supply):
                IGST = taxable_value * rate, and CGST/SGST must be 0.

        This verifies the *split*, not the rate itself (rate is an input).
        Fails closed on missing states or non-finite numeric inputs.
        """
        if not isinstance(supplier_state, str) or not supplier_state.strip():
            return {"verified": False, "error": "supplier_state is required."}
        if not isinstance(place_of_supply, str) or not place_of_supply.strip():
            return {"verified": False, "error": "place_of_supply is required."}

        try:
            value = parse_decimal_input(taxable_value, "taxable_value")
            rate = parse_decimal_input(gst_rate, "gst_rate")
            cgst = parse_decimal_input(claimed_cgst, "claimed_cgst")
            sgst = parse_decimal_input(claimed_sgst, "claimed_sgst")
            igst = parse_decimal_input(claimed_igst, "claimed_igst")
        except ValueError as exc:
            return {"verified": False, "error": str(exc)}

        if value < 0 or rate < 0:
            return {
                "verified": False,
                "error": "taxable_value and gst_rate must be non-negative.",
            }

        total_tax = value * rate / Decimal("100")
        is_interstate = supplier_state.strip().upper() != place_of_supply.strip().upper()

        if is_interstate:
            supply_type = "INTER_STATE"
            expected = {"cgst": Decimal("0"), "sgst": Decimal("0"), "igst": total_tax}
        else:
            supply_type = "INTRA_STATE"
            half = total_tax / Decimal("2")
            expected = {"cgst": half, "sgst": half, "igst": Decimal("0")}

        claimed = {"cgst": cgst, "sgst": sgst, "igst": igst}
        mismatches = [
            leg
            for leg in ("cgst", "sgst", "igst")
            if abs(claimed[leg] - expected[leg]) > self._SPLIT_TOLERANCE
        ]

        result = {
            "supply_type": supply_type,
            "expected": {leg: decimal_text(amount) for leg, amount in expected.items()},
            "claimed": {leg: decimal_text(amount) for leg, amount in claimed.items()},
        }

        if mismatches:
            wrong_type = (
                "CGST/SGST claimed on an inter-state supply"
                if is_interstate and (cgst or sgst)
                else "IGST claimed on an intra-state supply"
                if not is_interstate and igst
                else None
            )
            reason = (
                f"GST split mismatch on {supply_type} supply ({', '.join(mismatches)})."
            )
            if wrong_type:
                reason = f"{reason} {wrong_type}."
            result["verified"] = False
            result["error"] = reason
            return result

        result["verified"] = True
        return result


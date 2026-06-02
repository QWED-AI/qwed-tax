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

    _NUMERIC_FIELDS = (
        "taxable_value",
        "gst_rate",
        "claimed_cgst",
        "claimed_sgst",
        "claimed_igst",
    )

    @staticmethod
    def _parse_split_inputs(values: Dict[str, Any]) -> Dict[str, Decimal]:
        """Parse all numeric inputs to Decimal, rejecting negatives. Raises ValueError."""
        parsed: Dict[str, Decimal] = {}
        for field in GSTGuard._NUMERIC_FIELDS:
            amount = parse_decimal_input(values[field], field)
            if amount < 0:
                raise ValueError(f"{field} must be non-negative.")
            parsed[field] = amount
        return parsed

    @staticmethod
    def _expected_split(total_tax: Decimal, is_interstate: bool) -> Dict[str, Decimal]:
        if is_interstate:
            return {"cgst": Decimal("0"), "sgst": Decimal("0"), "igst": total_tax}
        half = total_tax / Decimal("2")
        return {"cgst": half, "sgst": half, "igst": Decimal("0")}

    @staticmethod
    def _wrong_type_note(is_interstate: bool, claimed: Dict[str, Decimal]) -> str:
        if is_interstate and (claimed["cgst"] or claimed["sgst"]):
            return "CGST/SGST claimed on an inter-state supply"
        if not is_interstate and claimed["igst"]:
            return "IGST claimed on an intra-state supply"
        return ""

    @classmethod
    def _leg_mismatch(cls, claimed: Decimal, expected: Decimal) -> bool:
        """
        A leg mismatches when it deviates from the expected amount.

        The rounding tolerance applies only to legs that carry tax (expected > 0),
        where half-rate division can leave a sub-paise remainder. Legs that must
        be exactly zero (the wrong tax type for the supply) get no tolerance, so
        even a tiny wrong-type amount is rejected.
        """
        if expected == 0:
            return claimed != 0
        return abs(claimed - expected) > cls._SPLIT_TOLERANCE

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
        Fails closed on missing states or non-finite/negative numeric inputs.
        """
        if not isinstance(supplier_state, str) or not supplier_state.strip():
            return {"verified": False, "error": "supplier_state is required."}
        if not isinstance(place_of_supply, str) or not place_of_supply.strip():
            return {"verified": False, "error": "place_of_supply is required."}

        try:
            parsed = self._parse_split_inputs(
                {
                    "taxable_value": taxable_value,
                    "gst_rate": gst_rate,
                    "claimed_cgst": claimed_cgst,
                    "claimed_sgst": claimed_sgst,
                    "claimed_igst": claimed_igst,
                }
            )
        except ValueError as exc:
            return {"verified": False, "error": str(exc)}

        total_tax = parsed["taxable_value"] * parsed["gst_rate"] / Decimal("100")
        is_interstate = (
            supplier_state.strip().upper() != place_of_supply.strip().upper()
        )

        expected = self._expected_split(total_tax, is_interstate)
        claimed = {
            "cgst": parsed["claimed_cgst"],
            "sgst": parsed["claimed_sgst"],
            "igst": parsed["claimed_igst"],
        }
        mismatches = [
            leg
            for leg in ("cgst", "sgst", "igst")
            if self._leg_mismatch(claimed[leg], expected[leg])
        ]

        result = {
            "supply_type": "INTER_STATE" if is_interstate else "INTRA_STATE",
            "expected": {leg: decimal_text(amount) for leg, amount in expected.items()},
            "claimed": {leg: decimal_text(amount) for leg, amount in claimed.items()},
        }

        if mismatches:
            reason = (
                f"GST split mismatch on {result['supply_type']} supply "
                f"({', '.join(mismatches)})."
            )
            note = self._wrong_type_note(is_interstate, claimed)
            if note:
                reason = f"{reason} {note}."
            result["verified"] = False
            result["error"] = reason
            return result

        result["verified"] = True
        return result



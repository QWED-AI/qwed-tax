from enum import Enum
from typing import Any, Callable, Dict, NamedTuple, Optional
from decimal import Decimal

from qwed_tax.audit import (
    RCM_DIRECTOR,
    RCM_GTA,
    RCM_IMPORT_SERVICE,
    RCM_LEGAL,
    RCM_NOT_APPLICABLE,
    RCM_RENTING_VEHICLE,
    RCM_SECURITY,
    RCM_SPONSORSHIP,
    RuleRef,
    build_trace,
)
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
    DIRECTOR = "DIRECTOR"  # Services by a director to the company
    SPONSORSHIP = "SPONSORSHIP"
    IMPORT_SERVICE = "IMPORT_SERVICE"  # Service imported from outside India
    OTHER = "OTHER"


class RCMRule(NamedTuple):
    """A declarative reverse-charge rule for one notified service."""

    # Predicate over (provider, recipient) deciding if RCM applies.
    applies: Callable[["EntityType", "EntityType"], bool]
    reason: str
    rule_ref: RuleRef

class GSTGuard:
    """
    Verifies GST Liability: Forward Charge (FCM) vs Reverse Charge (RCM).

    RCM applicability is expressed as a declarative table of notified
    services, each with its predicate and statutory reference. This keeps
    coverage auditable and easy to extend.
    """

    # Declarative RCM rule table. Models CGST Act, Section 9(3) notified
    # services (Notification 13/2017-CT(R) etc.). Section 9(4) (unregistered
    # supplier) is intentionally out of scope; IMPORT_SERVICE here is the
    # IGST-notification reverse charge (Notification 10/2017-IT(R)), not a 9(4)
    # path.
    _RCM_RULES: Dict["ServiceType", RCMRule] = {
        ServiceType.GTA: RCMRule(
            applies=lambda provider, recipient: recipient
            in (EntityType.BODY_CORPORATE, EntityType.PARTNERSHIP),
            reason="GTA service received by Body Corporate/Partnership attracts RCM.",
            rule_ref=RCM_GTA,
        ),
        ServiceType.LEGAL: RCMRule(
            applies=lambda provider, recipient: recipient
            in (EntityType.BODY_CORPORATE, EntityType.PARTNERSHIP),
            reason="Legal service to a Business Entity (Body Corporate/Partnership) attracts RCM.",
            rule_ref=RCM_LEGAL,
        ),
        ServiceType.SECURITY: RCMRule(
            applies=lambda provider, recipient: provider != EntityType.BODY_CORPORATE
            and recipient == EntityType.BODY_CORPORATE,
            reason="Security service by a Non-Body-Corporate to a registered person attracts RCM.",
            rule_ref=RCM_SECURITY,
        ),
        ServiceType.DIRECTOR: RCMRule(
            applies=lambda provider, recipient: recipient == EntityType.BODY_CORPORATE,
            reason="Services supplied by a director to the company attract RCM.",
            rule_ref=RCM_DIRECTOR,
        ),
        ServiceType.SPONSORSHIP: RCMRule(
            applies=lambda provider, recipient: recipient
            in (EntityType.BODY_CORPORATE, EntityType.PARTNERSHIP),
            reason="Sponsorship service to a Body Corporate/Partnership attracts RCM.",
            rule_ref=RCM_SPONSORSHIP,
        ),
        ServiceType.RENTING_VEHICLE: RCMRule(
            applies=lambda provider, recipient: provider != EntityType.BODY_CORPORATE
            and recipient == EntityType.BODY_CORPORATE,
            reason="Renting of a motor vehicle by a Non-Body-Corporate to a Body Corporate attracts RCM.",
            rule_ref=RCM_RENTING_VEHICLE,
        ),
        ServiceType.IMPORT_SERVICE: RCMRule(
            applies=lambda provider, recipient: True,
            reason="Import of service: the recipient in India is liable under RCM.",
            rule_ref=RCM_IMPORT_SERVICE,
        ),
    }

    def verify_rcm_applicability(
        self,
        service: ServiceType,
        provider: EntityType,
        recipient: EntityType,
        claimed_is_rcm: Optional[bool] = None,
    ) -> dict:
        """
        Determine who is liable to pay tax (forward charge vs reverse charge).

        Accepts either enum members or their raw string values (e.g. "GTA",
        "BODY_CORPORATE"), so JSON-sourced payloads work without pre-conversion.

        When claimed_is_rcm is provided, the function compares the computed RCM
        liability against the claim and returns verified=True only on exact match
        (verification mode). When omitted, returns a computed result with
        computed_only=True (calculation mode — backward compatible).
        """
        # Fail-closed on unknown service/entity — no silent coercion to defaults
        service_coerced = self._try_coerce(ServiceType, service)
        if service_coerced is None:
            return {
                "verified": False,
                "error": f"Unknown service type '{service}'. Cannot determine RCM applicability.",
                "is_rcm": None,
            }
        provider_coerced = self._try_coerce(EntityType, provider)
        if provider_coerced is None:
            return {
                "verified": False,
                "error": f"Unknown provider entity type '{provider}'. Cannot determine RCM applicability.",
                "is_rcm": None,
            }
        recipient_coerced = self._try_coerce(EntityType, recipient)
        if recipient_coerced is None:
            return {
                "verified": False,
                "error": f"Unknown recipient entity type '{recipient}'. Cannot determine RCM applicability.",
                "is_rcm": None,
            }

        service = service_coerced
        provider = provider_coerced
        recipient = recipient_coerced

        rule = self._RCM_RULES.get(service)
        is_rcm = bool(rule and rule.applies(provider, recipient))

        if is_rcm:
            reason = rule.reason
            rule_ref = rule.rule_ref
        else:
            reason = "Forward Charge (Provider pays)"
            rule_ref = RCM_NOT_APPLICABLE

        # Verification mode: compare computed RCM against claimed RCM
        if claimed_is_rcm is not None:
            if not isinstance(claimed_is_rcm, bool):
                return {
                    "verified": False,
                    "error": (
                        "Invalid claimed_is_rcm. Expected a boolean true/false "
                        "for deterministic verification."
                    ),
                    "is_rcm": is_rcm,
                }
            verified = (claimed_is_rcm is is_rcm)
            return {
                "verified": verified,
                "liability": "RECIPIENT (RCM)" if is_rcm else "PROVIDER (FCM)",
                "is_rcm": is_rcm,
                "claimed_is_rcm": claimed_is_rcm,
                "reason": reason,
                "error": None if verified else (
                    f"RCM mismatch: computed is_rcm={is_rcm}, claimed is_rcm={claimed_is_rcm}. {reason}"
                ),
                "audit_trace": build_trace(
                    rule_ref,
                    "REVERSE_CHARGE" if is_rcm else "FORWARD_CHARGE",
                    {
                        "service": service.value,
                        "provider": provider.value,
                        "recipient": recipient.value,
                        "claimed_is_rcm": claimed_is_rcm,
                    },
                ),
            }

        # Calculation mode (backward compatible) — computed, not verified against a claim
        return {
            "verified": False,
            "computed_only": True,
            "error": "Computed RCM only. Provide claimed_is_rcm for deterministic verification.",
            "liability": "RECIPIENT (RCM)" if is_rcm else "PROVIDER (FCM)",
            "is_rcm": is_rcm,
            "reason": reason,
            "audit_trace": build_trace(
                rule_ref,
                "REVERSE_CHARGE" if is_rcm else "FORWARD_CHARGE",
                {
                    "service": service.value,
                    "provider": provider.value,
                    "recipient": recipient.value,
                },
            ),
        }

    @staticmethod
    def _try_coerce(enum_cls, value):
        """Return an enum member or None if the value doesn't match any member."""
        if isinstance(value, enum_cls):
            return value
        try:
            return enum_cls(value)
        except (TypeError, ValueError):
            return None

    @staticmethod
    def _coerce(enum_cls, value, default):
        """Return an enum member for either an enum or its raw string value. (Legacy)"""
        if isinstance(value, enum_cls):
            return value
        try:
            return enum_cls(value)
        except ValueError:
            return default

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



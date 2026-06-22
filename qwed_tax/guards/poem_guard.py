from decimal import Decimal, ROUND_HALF_UP
from typing import Any, Dict

from qwed_tax.audit import POEM_CBDT_6_2017, POEM_SECTION_6_3, build_trace
from qwed_tax.diagnostics import TaxDiagnosticResult
from qwed_tax.numeric import decimal_text, parse_decimal_input

RATIO_SCALE = Decimal("0.0001")

class PoEMGuard:
    """
    Deterministic Guard for Place of Effective Management (PoEM).
    Used to determine tax residency of foreign companies.
    Ref: CBDT Circular 6 of 2017 (India), OECD Models.
    """
    
    def determine_residency(self, 
                          company_name: str,
                          is_foreign_incorp: bool,
                          turnover_total: Any,
                          turnover_outside_india: Any,
                          assets_total: Any,
                          assets_outside_india: Any,
                          employees_total: int,
                          employees_outside_india: int,
                          payroll_total: Any,
                          payroll_outside_india: Any,
                          key_management_location: str) -> Dict[str, Any]:
        """
        Determine if a foreign company is a Resident via PoEM.
        
        Rule (India):
        Foreign Company is Resident IF:
        1. Numeric turnover, asset, and payroll fields are well-formed.
        2. Fails "Active Business Outside India" (ABOI) test.
           ABOI Criteria (ALL must be true):
           - Assets Outside India >= 50%
           - Employees Outside India >= 50%
           - Payroll Outside India >= 50%
           
        AND
        3. Place of Effective Management is in India.
        """
        
        if not is_foreign_incorp:
            return {
                "verified": True,
                "residency": "RESIDENT",
                "reason": "Incorporated in India",
                "audit_trace": build_trace(POEM_SECTION_6_3, "DOMESTIC_COMPANY", {"company_name": company_name}),
            }

        parsed_values, error = self._parse_numeric_values(
            turnover_total,
            turnover_outside_india,
            assets_total,
            assets_outside_india,
            payroll_total,
            payroll_outside_india,
        )
        if error:
            return error

        employee_error = self._validate_employee_counts(
            employees_total, employees_outside_india
        )
        if employee_error:
            return employee_error

        value_error = self._validate_numeric_bounds(parsed_values)
        if value_error:
            return value_error

        # ABOI Test Checks
        # Note: 'Passive Income' check requires P&L data, here we simplify to Asset/Emp ratios as critical proxy.

        raw_assets_ratio, raw_emp_ratio, raw_payroll_ratio = self._compute_raw_ratios(
            parsed_values, employees_total, employees_outside_india
        )
        assets_ratio, emp_ratio, payroll_ratio = self._quantize_ratios(
            raw_assets_ratio, raw_emp_ratio, raw_payroll_ratio
        )
        
        is_aboi = (
            raw_assets_ratio >= Decimal("0.50")
            and raw_emp_ratio >= Decimal("0.50")
            and raw_payroll_ratio >= Decimal("0.50")
        )
        
        if is_aboi:
            # If Active Business is Outside India, PoEM is presumed Outside UNLESS majority board meetings in India.
            # For this guard, if ABOI is True, we generally treat as NON_RESIDENT unless forced.
            residency = "NON_RESIDENT"
            reason = "Company satisfies Active Business Outside India (ABOI) test."
        else:
            # Failed ABOI. Residency depends on Key Management Location.
            if key_management_location.upper() == "INDIA":
                residency = "RESIDENT"
                reason = "Fails ABOI test AND Key Management is in India (PoEM established)."
            else:
                residency = "NON_RESIDENT" # Even if fails ABOI, if decisions taken outside, then Non-Resident.
                reason = "Fails ABOI test BUT Key Management is Outside India."

        return {
            "verified": True,
            "residency": residency,
            "is_aboi": is_aboi,
            "metrics": {
                "assets_outside_ratio": decimal_text(assets_ratio),
                "employees_outside_ratio": decimal_text(emp_ratio),
                "payroll_outside_ratio": decimal_text(payroll_ratio),
            },
            "reason": reason,
            "audit_trace": build_trace(
                POEM_CBDT_6_2017,
                "RESIDENCY_DETERMINED",
                {
                    "residency": residency,
                    "is_aboi": is_aboi,
                    "assets_outside_ratio": decimal_text(assets_ratio),
                    "employees_outside_ratio": decimal_text(emp_ratio),
                    "payroll_outside_ratio": decimal_text(payroll_ratio),
                    "key_management_location": key_management_location,
                },
            ),
        }

    @staticmethod
    def to_diagnostic(result: Dict[str, Any]) -> TaxDiagnosticResult:
        """Convert a legacy determine_residency() dict to TaxDiagnosticResult."""
        verified = result.get("verified", False)
        audit_trace = result.get("audit_trace")

        if not verified:
            return TaxDiagnosticResult.blocked(
                agent_message="PoEM residency verification could not be completed.",
                developer_fields={
                    "constraint_id": audit_trace["rule_id"] if audit_trace else "POEM_UNKNOWN",
                    "audit_trace": audit_trace,
                    "residency": result.get("residency"),
                    "reason": result.get("reason"),
                },
            )

        if audit_trace is None:
            raise ValueError(
                "VERIFIED result requires audit_trace — "
                "use UNVERIFIABLE if no evidence was established."
            )

        return TaxDiagnosticResult.verified(
            agent_message="PoEM residency verified.",
            developer_fields={
                "constraint_id": audit_trace["rule_id"],
                "statute": audit_trace.get("statute"),
                "jurisdiction": audit_trace.get("jurisdiction"),
                "audit_trace": audit_trace,
                "residency": result.get("residency"),
                "is_aboi": result.get("is_aboi"),
                "metrics": result.get("metrics"),
                "reason": result.get("reason"),
            },
            evidence=audit_trace,
        )

    def _parse_numeric_values(
        self,
        turnover_total: Any,
        turnover_outside_india: Any,
        assets_total: Any,
        assets_outside_india: Any,
        payroll_total: Any,
        payroll_outside_india: Any,
    ) -> tuple[Dict[str, Decimal] | None, Dict[str, Any] | None]:
        try:
            # Turnover fields are currently validated for input-shape hygiene only; ABOI uses asset, employee, and payroll ratios.
            parse_decimal_input(turnover_total, "turnover_total")
            parse_decimal_input(turnover_outside_india, "turnover_outside_india")
            return (
                {
                    "assets_total": parse_decimal_input(assets_total, "assets_total"),
                    "assets_outside": parse_decimal_input(assets_outside_india, "assets_outside_india"),
                    "payroll_total": parse_decimal_input(payroll_total, "payroll_total"),
                    "payroll_outside": parse_decimal_input(payroll_outside_india, "payroll_outside_india"),
                },
                None,
            )
        except ValueError as exc:
            return None, self._unverifiable(str(exc))

    def _validate_employee_counts(
        self, employees_total: int, employees_outside_india: int
    ) -> Dict[str, Any] | None:
        if employees_total < 0 or employees_outside_india < 0:
            return self._unverifiable("employee counts must be non-negative integers.")
        if employees_outside_india > employees_total:
            return self._unverifiable(
                "employees_outside_india cannot exceed employees_total."
            )
        return None

    def _validate_numeric_bounds(
        self, values: Dict[str, Decimal]
    ) -> Dict[str, Any] | None:
        if values["assets_total"] < 0 or values["assets_outside"] < 0:
            return self._unverifiable("asset values must be non-negative numeric values.")
        if values["assets_outside"] > values["assets_total"]:
            return self._unverifiable(
                "assets_outside_india cannot exceed assets_total."
            )
        if values["payroll_total"] < 0 or values["payroll_outside"] < 0:
            return self._unverifiable(
                "payroll values must be non-negative numeric values."
            )
        if values["payroll_outside"] > values["payroll_total"]:
            return self._unverifiable(
                "payroll_outside_india cannot exceed payroll_total."
            )
        return None

    def _compute_raw_ratios(
        self,
        values: Dict[str, Decimal],
        employees_total: int,
        employees_outside_india: int,
    ) -> tuple[Decimal, Decimal, Decimal]:
        assets_ratio = (
            values["assets_outside"] / values["assets_total"]
            if values["assets_total"] > Decimal("0")
            else Decimal("0")
        )
        emp_ratio = (
            Decimal(employees_outside_india) / Decimal(employees_total)
            if employees_total > 0
            else Decimal("0")
        )
        payroll_ratio = (
            values["payroll_outside"] / values["payroll_total"]
            if values["payroll_total"] > Decimal("0")
            else Decimal("0")
        )
        return assets_ratio, emp_ratio, payroll_ratio

    def _quantize_ratios(
        self, assets_ratio: Decimal, emp_ratio: Decimal, payroll_ratio: Decimal
    ) -> tuple[Decimal, Decimal, Decimal]:
        return (
            assets_ratio.quantize(RATIO_SCALE, rounding=ROUND_HALF_UP).normalize(),
            emp_ratio.quantize(RATIO_SCALE, rounding=ROUND_HALF_UP).normalize(),
            payroll_ratio.quantize(RATIO_SCALE, rounding=ROUND_HALF_UP).normalize(),
        )

    def _unverifiable(self, reason: str) -> Dict[str, Any]:
        return {
            "verified": False,
            "residency": "UNVERIFIABLE",
            "reason": reason,
            "audit_trace": build_trace(POEM_CBDT_6_2017, "INPUT_VALIDATION_FAILED", {"reason": reason}),
        }

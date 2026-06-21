"""Tests for middleware partial-verification fix (#19) and TaxPreFlight checks_not_run."""

from qwed_tax.middleware.gusto_interceptor import QWEDTaxMiddleware
from qwed_tax.verifier import TaxPreFlight


class TestMiddlewareArithmeticOnly:
    """Middleware must not overstate arithmetic verification as full tax verification."""

    def setup_method(self):
        self.mw = QWEDTaxMiddleware()

    def _valid_payroll_payload(self):
        return {
            "payroll_entry": {
                "employee_id": "E001",
                "gross_pay": "5000.00",
                "taxes": [
                    {"name": "Federal Income Tax", "amount": "800.00"},
                    {"name": "Social Security", "amount": "310.00"},
                ],
                "deductions": [
                    {"name": "401k", "amount": "500.00", "type": "PRE_TAX"},
                ],
                "net_pay_claimed": "3390.00",
                "currency": "USD",
            }
        }

    def test_success_status_is_arithmetic_verified_not_verified(self):
        res = self.mw.process_ai_payroll_request(self._valid_payroll_payload())
        assert res["status"] == "ARITHMETIC_VERIFIED"
        assert res["status"] != "VERIFIED"

    def test_success_blocks_execution(self):
        res = self.mw.process_ai_payroll_request(self._valid_payroll_payload())
        assert res["execution_permitted"] is False

    def test_success_lists_checks_run(self):
        res = self.mw.process_ai_payroll_request(self._valid_payroll_payload())
        assert res["checks_run"] == ["gross_to_net_arithmetic"]

    def test_success_lists_checks_not_run(self):
        res = self.mw.process_ai_payroll_request(self._valid_payroll_payload())
        assert "worker_classification" in res["checks_not_run"]
        assert "withholding_legality" in res["checks_not_run"]
        assert "reciprocity" in res["checks_not_run"]
        assert "filing_obligations" in res["checks_not_run"]

    def test_block_on_missing_payload(self):
        res = self.mw.process_ai_payroll_request({})
        assert res["status"] == "BLOCKED"
        assert res["execution_permitted"] is False

    def test_block_on_invalid_schema(self):
        res = self.mw.process_ai_payroll_request({"payroll_entry": {"bad": "data"}})
        assert res["status"] == "BLOCKED"
        assert res["execution_permitted"] is False

    def test_block_on_arithmetic_failure(self):
        payload = self._valid_payroll_payload()
        payload["payroll_entry"]["net_pay_claimed"] = "9999.00"
        res = self.mw.process_ai_payroll_request(payload)
        assert res["status"] == "BLOCKED"
        assert res["execution_permitted"] is False


class TestTaxPreFlightChecksNotRun:
    """TaxPreFlight must report checks_not_run for transparency (#19)."""

    def setup_method(self):
        self.pf = TaxPreFlight()

    def test_hire_action_lists_known_gaps(self):
        intent = {
            "action": "hire",
            "worker_type": "W2",
            "worker_facts": {
                "provides_tools": False,
                "reimburses_expenses": True,
                "indefinite_relationship": True,
            },
        }
        report = self.pf.audit_transaction(intent)
        assert "checks_not_run" in report
        assert "payroll_arithmetic" in report["checks_not_run"]
        assert "withholding_legality" in report["checks_not_run"]
        assert "reciprocity" in report["checks_not_run"]
        assert "filing_obligations" in report["checks_not_run"]

    def test_pay_invoice_action_lists_known_gaps(self):
        intent = {
            "action": "pay_invoice",
            "service_type": "professional_services",
            "amount": "50000",
            "ytd_payment": "100000",
        }
        report = self.pf.audit_transaction(intent)
        assert "checks_not_run" in report
        assert "itc_eligibility" in report["checks_not_run"]
        assert "gst_split" in report["checks_not_run"]
        assert "rcm_applicability" in report["checks_not_run"]

    def test_trade_tax_lists_unselected_checks(self):
        intent = {
            "action": "trade_tax",
            "loss_head": "intraday",
            "offset_head": "f&o",
            "loss_amount": "5000",
        }
        report = self.pf.audit_transaction(intent)
        assert "checks_not_run" in report
        assert "capital_gains" in report["checks_not_run"]

    def test_blocked_report_has_checks_not_run(self):
        report = self.pf.audit_transaction({"action": "unknown_action"})
        assert "checks_not_run" in report
        assert report["checks_not_run"] == []

    def test_selected_but_missing_fields_lists_in_checks_not_run(self):
        intent = {
            "action": "trade_tax",
            "asset_type": "equity",
            "dates": {"buy": "2023-01-01"},
            "claimed_rate": "12.5",
        }
        report = self.pf.audit_transaction(intent)
        assert report["allowed"] is False
        assert "capital_gains" in report["checks_not_run"]

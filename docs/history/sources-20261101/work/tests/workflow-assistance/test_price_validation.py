"""Offline synthetic-input tests for the WL-R07 price-record validation layer.

Drives services/radar/price_validation.py with in-memory data only: no real
billing data, no provider, no network, no payment.  Covers the four boundary
defects the 2026-09-15 workbook audit reproduced in-memory plus the
unknown-cost-must-not-be-0 rule.
"""
import importlib.util
import sys
import unittest
from pathlib import Path

# Repo convention: gate runs this file directly, so services/ is not a
# resolvable package on sys.path. Load the module by file path instead of
# `from services.radar import price_validation` (root-cause of CI run
# 34993528858 ModuleNotFoundError: No module named 'services').
# NOTE: register in sys.modules BEFORE exec_module — price_validation.py
# defines @dataclass objects and dataclasses._is_type resolves
# sys.modules[cls.__module__]; an unregistered exec'd module raises
# AttributeError there. (Same pre-registration test_radar.py._load uses.)
_PV = Path(__file__).resolve().parents[2] / "services" / "radar" / "price_validation.py"
_spec = importlib.util.spec_from_file_location("price_validation", _PV)
pv = importlib.util.module_from_spec(_spec)
sys.modules["price_validation"] = pv
_spec.loader.exec_module(pv)


class PriceValidationTests(unittest.TestCase):
    def test_integer_call_count_ok(self):
        self.assertTrue(pv.validate_call_count(42).ok)

    def test_zero_call_count_is_valid(self):
        # 0 is a legitimate "nothing called yet"; only the task-price side
        # (pass_rate over 0 attempts) is the no-price case, not a data error.
        self.assertTrue(pv.validate_call_count(0).ok)

    def test_unknown_call_count_rejected(self):
        r = pv.validate_call_count(None)
        self.assertFalse(r.ok)
        self.assertIn("unknown", r.errors[0])

    def test_fractional_call_count_rejected(self):
        self.assertFalse(pv.validate_call_count(2.5).ok)
        self.assertFalse(pv.validate_call_count(2.0).ok)  # whole-valued float is still a type error
        self.assertFalse(pv.validate_call_count(True).ok)  # bool is not a count

    def test_negative_call_count_rejected(self):
        self.assertFalse(pv.validate_call_count(-1).ok)

    def test_pass_rate_bounds(self):
        self.assertTrue(pv.validate_pass_rate(0.0).ok)
        self.assertTrue(pv.validate_pass_rate(1.0).ok)
        self.assertFalse(pv.validate_pass_rate(1.5).ok)
        self.assertFalse(pv.validate_pass_rate(-0.1).ok)
        self.assertFalse(pv.validate_pass_rate(None).ok)

    def test_negative_duration_rejected(self):
        r = pv.validate_duration(-3.0, kind="voice")
        self.assertFalse(r.ok)
        self.assertTrue(any("negative" in e for e in r.errors))

    def test_unknown_duration_rejected(self):
        self.assertFalse(pv.validate_duration(None).ok)

    def test_zero_duration_is_valid(self):
        self.assertTrue(pv.validate_duration(0).ok)

    def test_unknown_price_is_honest_not_zero(self):
        # A None amount is a VALID honest UNKNOWN, not an error — the guard
        # against "unknown rendered as 0" is that we never coerce None->0.
        r = pv.validate_price(None, currency="USD")
        self.assertTrue(r.ok)
        self.assertIn("UNKNOWN", r.reasons[0])

    def test_negative_price_rejected(self):
        self.assertFalse(pv.validate_price(-5.0, currency="USD").ok)

    def test_concrete_price_requires_currency(self):
        self.assertFalse(pv.validate_price(3.0, currency="").ok)
        self.assertTrue(pv.validate_price(3.0, currency="USD").ok)

    def test_zero_denominator_gives_explicit_error_not_div0(self):
        r = pv.compute_price(12.0, 0, currency="USD")
        self.assertFalse(r.ok)
        self.assertIn("denominator is zero", r.errors[0])
        # the whole point: an explicit REJECTED, not a 0 / nan / #DIV/0!
        self.assertNotIn("#DIV", str(r.errors))

    def test_unknown_unit_price_is_unknown_result(self):
        r = pv.compute_price(None, 10, currency="USD")
        self.assertTrue(r.ok)
        self.assertIn("UNKNOWN", r.reasons[0])

    def test_valid_price_computation(self):
        r = pv.compute_price(12.0, 3, currency="USD")
        self.assertTrue(r.ok)
        self.assertAlmostEqual(r.value, 4.0)

    def test_full_record_all_ok(self):
        rec = {"calls": 10, "pass_rate": 0.9, "amount": 2.5, "currency": "USD"}
        self.assertTrue(pv.validate_price_record(rec).ok)

    def test_full_record_collects_multiple_violations(self):
        rec = {"calls": 0.5, "pass_rate": 2.0, "amount": -1, "currency": ""}
        r = pv.validate_price_record(rec)
        self.assertFalse(r.ok)
        self.assertGreaterEqual(len(r.errors), 3)

    def test_full_record_unknown_amount_honest(self):
        rec = {"calls": 5, "amount": None, "currency": "USD"}
        r = pv.validate_price_record(rec)
        self.assertTrue(r.ok)  # unknown cost stays an honest UNKNOWN, not an error

    def test_to_dict_round_trip(self):
        r = pv.validate_price_record({"calls": 0.5})
        d = r.to_dict()
        self.assertEqual(d["verdict"], "rejected")
        self.assertIsInstance(d["errors"], list)


if __name__ == "__main__":
    unittest.main()

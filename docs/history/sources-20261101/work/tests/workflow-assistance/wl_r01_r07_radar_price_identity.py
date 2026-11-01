"""WL-R01 / WL-R07 offline radar reuse-loop + price-identity contract tests.

Pure, deterministic, no network / no paid calls / no sibling import (gate-safe,
following the NF-02 convention).  Proves the two card deliverables without
inventing a second radar platform:

  WL-R01  Replaying the same fixed sample mints NO duplicate candidates; a
          version change is explainable (superseded / conflict / unchanged);
          evidence below B is never reported as high confidence; nothing is
          auto-promoted to a PoC / task pack / PR / install.
  WL-R07  Price identity: model/provider/currency/effective_at/source/version
          are preserved, missing items are stamped the UNKNOWN sentinel (never
          collapsed to 0 or ""), an unknown amount is never rendered as a
          concrete zero, and the superseded value keeps its validity window.
"""
from __future__ import annotations

import importlib.util
import os
import sys
import unittest

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
MOD = os.path.join(ROOT, "services", "radar", "radar_reuse_loop.py")


def _load():
    spec = importlib.util.spec_from_file_location("radar_reuse_loop", MOD)
    m = importlib.util.module_from_spec(spec)
    sys.modules["radar_reuse_loop"] = m
    spec.loader.exec_module(m)
    return m


def _c(url="https://repo/a/b", **kw):
    base = {
        "canonical_url": url, "owner": "a", "repo": "b",
        "license": "MIT", "version": "1.2.0", "evidence_level": "A",
        "project_need": "reference",
    }
    base.update(kw)
    return base


class RadarReuseLoopTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.m = _load()

    # ---- WL-R01 ---------------------------------------------------------
    def test_replay_mints_no_duplicate_candidates(self):
        sample = [_c("https://repo/a/b"), _c("https://repo/a/b"), _c("https://repo/a/c")]
        r1 = self.m.build_offline_loop(sample)
        r2 = self.m.build_offline_loop(sample)
        self.assertEqual(r1["candidate_count"], 2)  # a/b deduped to one
        self.assertEqual(r1["receipt_sha256"], r2["receipt_sha256"])  # deterministic
        self.assertTrue(r1["no_duplicate_candidates"])

    def test_version_change_is_explainable_superseded(self):
        before = {"https://repo/a/b": {"version": "1.0.0", "license": "MIT", "price": None}}
        after_sample = [_c("https://repo/a/b", version="2.0.0")]
        cur = self.m.dedupe_candidates(after_sample)
        cur_view = {cur[0]["canonical_url"]: {"version": "2.0.0", "commit": None, "license": "MIT", "price": None}}
        diff = self.m.version_diff(before, cur_view)
        self.assertEqual(diff["https://repo/a/b"]["relation"], "superseded")
        self.assertIn("version", diff["https://repo/a/b"]["changed_fields"])

    def test_same_version_disagreement_is_conflict(self):
        before = {"k": {"version": "1.0.0", "license": "MIT", "price": None}}
        after = {"k": {"version": "1.0.0", "license": "Apache-2.0", "price": None}}
        diff = self.m.version_diff(before, after)
        self.assertEqual(diff["k"]["relation"], "conflict")
        self.assertIn("license", diff["k"]["changed_fields"])

    def test_insufficient_evidence_is_never_high_confidence(self):
        r = self.m.build_offline_loop([_c("k", evidence_level="C")])
        self.assertFalse(r["all_evidence_honest"] is False)  # honest
        self.assertEqual(r["candidates"][0]["high_confidence"], False)
        # evidence A is high confidence
        ra = self.m.build_offline_loop([_c("k", evidence_level="A")])
        self.assertEqual(ra["candidates"][0]["high_confidence"], True)

    def test_reuse_verdicts_and_no_auto_promotion(self):
        m = self.m
        self.assertEqual(m.classify_reuse(_c(project_need="direct_dependency", has_real_call_or_dep=True))["verdict"], "DIRECT_DEPENDENCY")
        self.assertEqual(m.classify_reuse(_c(project_need="provider"))["verdict"], "PROVIDER")
        self.assertEqual(m.classify_reuse(_c(project_need="adapter"))["verdict"], "ADAPTER")
        self.assertEqual(m.classify_reuse(_c(project_need="algorithm"))["verdict"], "ALGORITHM_DONOR")
        self.assertEqual(m.classify_reuse(_c(project_need="reference"))["verdict"], "REFERENCE_ONLY")
        rejected = m.classify_reuse(_c(project_need="", project_fit="不绑定当前任务"))
        self.assertEqual(rejected["verdict"], "REJECTED")
        self.assertTrue(rejected["retire_reason"])
        for verdict in (m.classify_reuse(_c(project_need="provider")),
                        m.classify_reuse(_c(project_need="reference"))):
            self.assertFalse(verdict["auto_promoted"])  # never auto PoC/PR/install

    # ---- WL-R07 ---------------------------------------------------------
    def test_missing_identity_stamps_unknown_never_zero(self):
        n = self.m.normalize_price_identity({"amount": 10.0, "currency": "USD"})
        # provider / model / effective_at / source / version all missing -> UNKNOWN
        self.assertEqual(n["identity"]["provider"], self.m.UNKNOWN)
        self.assertEqual(n["identity"]["model"], self.m.UNKNOWN)
        self.assertEqual(n["identity"]["effective_at"], self.m.UNKNOWN)
        self.assertEqual(n["unknown_propagates"], True)
        self.assertEqual(n["display"], 10.0)  # concrete figure shown

    def test_unknown_amount_never_rendered_as_zero(self):
        n = self.m.normalize_price_identity({"amount": None, "currency": "USD", "provider": "p"})
        self.assertTrue(n["figure"]["is_unknown"])
        self.assertEqual(n["display"], self.m.UNKNOWN)  # not 0
        self.assertTrue(n["figure"]["never_rendered_as_zero"])

    def test_zero_amount_is_known_zero_not_unknown(self):
        n = self.m.normalize_price_identity({"amount": 0, "currency": "USD", "provider": "p"})
        self.assertFalse(n["figure"]["is_unknown"])
        self.assertEqual(n["display"], 0)

    def test_entitlement_subscription_api_consumption_lanes_separated(self):
        n = self.m.normalize_price_identity({
            "amount": 5.0, "currency": "USD", "provider": "p",
            "entitlement": "pro-plan", "subscription": True, "real_consumption": "2 calls",
        })
        lanes = n["lanes"]
        self.assertEqual(lanes["entitlement"], "pro-plan")
        self.assertEqual(lanes["subscription"], True)
        self.assertEqual(lanes["api_price"], 5.0)
        self.assertEqual(lanes["real_consumption"], "2 calls")

    def test_superseded_value_keeps_validity_window(self):
        n = self.m.normalize_price_identity({
            "amount": 8.0, "currency": "USD", "provider": "p",
            "superseded": {"amount": 3.0, "valid_from": "2026-01-01",
                           "valid_to": "2026-06-01", "as_of": "2026-05-01"},
        })
        self.assertEqual(n["superseded_identity"]["value"], 3.0)
        self.assertEqual(n["superseded_identity"]["valid_from"], "2026-01-01")
        self.assertEqual(n["superseded_identity"]["valid_to"], "2026-06-01")

    def test_price_receipt_is_deterministic(self):
        rec = {"amount": 4.0, "currency": "CNY", "provider": "ds", "model": "deepseek"}
        a = self.m.price_receipt(rec)
        b = self.m.price_receipt(rec)
        self.assertEqual(a["receipt_sha256"], b["receipt_sha256"])

    def test_workbook_entity_absent_honest(self):
        # WL-R07: the xlsx workbook entity is NOT in the repo; do not fake results.
        wb = os.path.join(ROOT, "03_价格与额度工作簿.xlsx")
        present = os.path.exists(wb)
        self.assertFalse(present, "workbook entity unexpectedly present — re-scope")
        # The price chain proves its boundary offline; workbook UI/comma-compat
        # stay UNVERIFIED until the entity is provided + opened in Excel/WPS.
        self.assertEqual(self.m.normalize_price_identity({"amount": None})["display"], self.m.UNKNOWN)


if __name__ == "__main__":
    unittest.main(verbosity=2)

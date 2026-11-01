"""NF-05 / NF-06 scoped-verification contract tests (integrated-taskpack-20260916).

NF-05: every *supported* client action carries real version + entry evidence,
and an unsupported feature is NOT displayed as "adapted".  The user's
provider/model/reasoning choice is never silently rewritten, cross-profile
writes are forbidden, the Open Design client and the DESIGN-LAB project keep
two separate identities, and CC Switch stays observe-only.

NF-06: one real client's read-only value closed loop — probe evidence rolls up
into a desensitized write-free receipt, and applying that receipt is a no-op
(a read-only version must never be called a deployment).

Repo convention (NF-02 lesson): the service module is loaded by file path,
NOT via a `from services...` package import, because the gate runs this test
file directly with services/ not on sys.path.  These tests read
config-ownership.json as plain data (no import) so they lock the semantic
contracts against silent weakening.
"""
from __future__ import annotations

import importlib.util
import json
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def _load(name: str, module_name: str):
    spec = importlib.util.spec_from_file_location(module_name, ROOT / "services" / "policy" / name)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    sys.modules[module_name] = module
    spec.loader.exec_module(module)
    return module


_RCV = _load("readonly_client_value.py", "rcv")
OWNERSHIP = json.loads((ROOT / "config" / "config-ownership.json").read_text(encoding="utf-8"))
CONFORMANCE = json.loads((ROOT / "config" / "capability-conformance.json").read_text(encoding="utf-8"))


class NF05OwnershipContractsTests(unittest.TestCase):
    """Lock the client-identity / routing semantics against silent weakening."""

    def test_cc_switch_stays_observe_only(self):
        self.assertEqual(OWNERSHIP["adapter_defaults"]["cc-switch"]["mode"], "OBSERVE")
        self.assertTrue(OWNERSHIP["adapter_defaults"]["cc-switch"]["preserve_unknown"])
        # CC Switch owns only supported-client provider routing — it never
        # becomes a unified API token or a write surface.
        self.assertTrue(OWNERSHIP["rules"]["cc_switch_owns_supported_client_provider_routing_only"])

    def test_open_design_client_and_design_lab_project_are_separate_identities(self):
        self.assertEqual(OWNERSHIP["adapter_defaults"]["open-design"]["mode"], "OBSERVE")
        # the capability is owned by the Open Design *project*, not the client
        self.assertTrue(OWNERSHIP["rules"]["open_design_capability_owned_by_open_design_project"])

    def test_cross_client_sync_is_forbidden(self):
        self.assertTrue(OWNERSHIP["rules"]["cross_client_prompt_skill_session_sync_forbidden"])
        self.assertTrue(OWNERSHIP["rules"]["raw_memory_never_crosses_client_boundary"])

    def test_user_choice_cannot_be_silently_weakened(self):
        # provider/model/reasoning follow the user's native choice; the user
        # overlay may not weaken official security, and unknown fields default
        # to OBSERVE+quarantine (never silently deleted).
        self.assertTrue(OWNERSHIP["rules"]["user_overlay_cannot_weaken_official_security"])
        self.assertEqual(OWNERSHIP["default_unknown"], {"mode": "OBSERVE", "quarantine": True})
        self.assertTrue(OWNERSHIP["rules"]["secret_never_collected"])

    def test_observe_only_clients_have_no_write_surface(self):
        # an OBSERVE-mode client's value receipt must report write_surface=False
        for client in ("cc-switch", "github", "openhuman", "open-design"):
            rep = _RCV.build_readonly_value_report(
                client,
                {"installed": True, "version": "1.0", "capabilities": ["observe"]},
                OWNERSHIP, CONFORMANCE,
            )
            self.assertEqual(rep["write_surface"], False, client)
            self.assertEqual(rep["ownership_mode"], "OBSERVE")


class NF05CapabilityGapTests(unittest.TestCase):
    """NF-05 acceptance pt.1: no 'adapted' claim without version + entry evidence."""

    def test_supported_action_carries_version_and_entry_evidence(self):
        rep = _RCV.build_readonly_value_report(
            "hermes",
            {"installed": True, "version": "0.21.2",
             "capabilities": ["run_status", "token_usage"], "evidence_level": "A"},
            OWNERSHIP, CONFORMANCE,
        )
        self.assertEqual(rep["version"], "0.21.2")
        self.assertIn("run_status", rep["supported_actions"])
        self.assertEqual(rep["capability_gaps"], [])

    def test_unsupported_feature_is_a_named_gap_not_adapted(self):
        rep = _RCV.build_readonly_value_report(
            "codex",
            {"installed": True, "version": "0.154",
             "capabilities": ["run_status"]},
            OWNERSHIP, CONFORMANCE,
        )
        # token_usage was not probed -> an honest named gap
        self.assertIn("token_usage", rep["capability_gaps"])
        self.assertIn("UNSUPPORTED", rep["next_step"])
        # it is NOT listed as a supported action
        self.assertNotIn("token_usage", rep["supported_actions"])

    def test_version_not_evidenced_is_never_assumed(self):
        rep = _RCV.build_readonly_value_report(
            "codex",
            {"installed": True, "version": None, "capabilities": ["run_status"]},
            OWNERSHIP, CONFORMANCE,
        )
        self.assertIsNone(rep["version"])
        self.assertIn("version-not-evidenced", rep["next_step"])

    def test_unverified_protocol_views_are_surfaced(self):
        rep = _RCV.build_readonly_value_report(
            "hermes",
            {"installed": True, "version": "0.21.2", "capabilities": []},
            OWNERSHIP, CONFORMANCE,
        )
        # mcp is STATIC_UNVERIFIED in the conformance view -> must surface
        self.assertTrue(any(v.startswith("mcp=") for v in rep["conformance_unverified"]))


class NF06ReadOnlyValueLoopTests(unittest.TestCase):
    """NF-06: one real client's read-only value closed loop, write-free."""

    def test_hermes_readonly_loop_produces_desensitized_receipt(self):
        rep = _RCV.build_readonly_value_report(
            "hermes",
            {"installed": True, "version": "0.21.2",
             "capabilities": ["run_status", "token_usage", "observe"]},
            OWNERSHIP, CONFORMANCE,
        )
        self.assertEqual(rep["client"], "hermes")
        self.assertTrue(rep["installed"])
        self.assertEqual(rep["privacy"], "metadata-only")
        # a MANAGE-mode client does have a write surface flag, but the receipt
        # itself still cannot be applied (it is an observation, not a write).
        self.assertEqual(rep["ownership_mode"], "MANAGE")

    def test_applying_a_readonly_receipt_is_an_explicit_noop(self):
        rep = _RCV.build_readonly_value_report(
            "open-design",
            {"installed": True, "version": "0.23.1", "capabilities": ["observe"]},
            OWNERSHIP, CONFORMANCE,
        )
        r = _RCV.apply_receipt(rep)
        self.assertEqual(r["status"], "OBSERVED_ONLY")
        self.assertFalse(r["applied"])
        # never a fake success / deployment
        self.assertNotIn("APPLIED", r["status"])

    def test_simulated_report_is_tagged_and_never_real(self):
        sim = _RCV.build_readonly_value_report(
            "hermes",
            {"installed": True, "version": "0.21.2", "capabilities": ["run_status"]},
            OWNERSHIP, CONFORMANCE, simulated=True,
        )
        real = _RCV.build_readonly_value_report(
            "hermes",
            {"installed": True, "version": "0.21.2", "capabilities": ["run_status"]},
            OWNERSHIP, CONFORMANCE, simulated=False,
        )
        self.assertTrue(sim["simulated"])
        self.assertFalse(real["simulated"])
        # a real-only value tally must exclude the simulated receipt
        tally = [x for x in (sim, real) if not x["simulated"]]
        self.assertEqual(len(tally), 1)


if __name__ == "__main__":
    unittest.main()

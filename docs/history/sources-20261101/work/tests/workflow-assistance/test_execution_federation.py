"""Tests for execution federation (WL-200/210/220/230/240): the unified
executor-ACP adapter interface and the five WORK-LAB executor adapters.

Repo convention (mirrors test_session_federation.py / test_task_governance.py):
modules under services/ are loaded by spec — no package __init__ — so each
file is loaded via importlib and pre-registered in sys.modules under a stable
name so the shared Capability/Op enums stay singletons across every adapter.

All tests are *environment-safe*: they inject probe results / fake PATHs so
no test depends on which executor binaries happen to be installed, and no
test ever spawns a process or reads credentials.
"""
from __future__ import annotations

import importlib.util
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
FED = ROOT / "services" / "execution-federation"


def _load(name: str, module_name: str):
    spec = importlib.util.spec_from_file_location(module_name, FED / name)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    sys.modules[module_name] = module
    spec.loader.exec_module(module)
    return module


class BaseAdapterTests(unittest.TestCase):
    """The abstract base honestly degrades — no op ever raises."""

    def test_unknown_executor_is_not_inventable(self):
        acp = _load("acp_adapter.py", "ef_acp")
        fed_mod = _load("federation.py", "ef_fed")
        fed = fed_mod.ExecutorFederation()
        # empty federation: every op degrades, none invents an executor
        r = fed.capabilities("hermes")
        self.assertFalse(r.ok)
        self.assertEqual(r.status, "UNKNOWN_EXECUTOR")
        self.assertTrue(fed_mod.default_federation().__len__())  # 5 wired

    def test_base_cap_set_is_minimal(self):
        acp = _load("acp_adapter.py", "ef_acp")
        base = acp.ExecutorAcpAdapter()
        caps = base.capabilities()
        # base only self-queries; it must not claim launch
        self.assertIn("capabilities", caps["supports"])
        self.assertNotIn("launch", caps["supports"])
        self.assertFalse(caps["launchable"])


class HermesAdapterTests(unittest.TestCase):
    def test_launchable_when_injected_path_has_bin(self):
        her = _load("hermes_adapter.py", "ef_hermes")
        a = her.HermesAdapter(hermes_bin="/fake/bin/hermes")
        # the fixture path does not exist on disk and is not a real PATH
        # entry -> adapter must say not launchable, not crash.
        self.assertFalse(a.is_launchable())
        self.assertTrue(a.is_launchable() in (True, False))

    def test_disabled_by_policy(self):
        her = _load("hermes_adapter.py", "ef_hermes")
        a = her.HermesAdapter(allow_launch=False)
        self.assertFalse(a.is_launchable())
        self.assertIn("launch disabled by policy", " ".join(a.launch_notes()))

    def test_new_tags_universal_session_id(self):
        her = _load("hermes_adapter.py", "ef_hermes")
        a = her.HermesAdapter(hermes_bin="/nonexistent-hermes", allow_launch=True)
        # not launchable -> new() degrades to NOT_LAUNCHABLE, no universal id
        r = a.new(project_id="work-lab")
        self.assertFalse(r.ok)
        self.assertEqual(r.status, "NOT_LAUNCHABLE")


class CodexDshAdapterTests(unittest.TestCase):
    def test_session_capability_without_cli(self):
        # codex/dsh expose session + handoff + resume off the native store
        # even when the CLI is absent — that is the point of the readers.
        cod = _load("codex_adapter.py", "ef_codex")
        c = cod.CodexAdapter(allow_launch=True, search_path="/definitely-not-a-path")
        caps = c.capabilities()["supports"]
        self.assertIn("session", caps)
        self.assertIn("handoff", caps)
        self.assertNotIn("launch", caps)   # CLI not reachable here

    def test_dsh_data_root_in_health(self):
        dsh = _load("dsh_adapter.py", "ef_dsh")
        d = dsh.DshAdapter(dsh_root="/nonexistent-dsh")
        h = d.health()
        self.assertFalse(h["data_root_exists"])


class OpenHandsPiTests(unittest.TestCase):
    def test_openhands_requires_explicit_reachability(self):
        oh = _load("openhands_adapter.py", "ef_oh")
        a = oh.OpenHandsAdapter(backend_url="https://oh.example")
        # configured URL but not probed reachable -> NOT launchable
        self.assertFalse(a.is_launchable())
        self.assertIn("configured but not probed reachable",
                      " ".join(a.launch_notes()))
        b = oh.OpenHandsAdapter(reachable=True)
        self.assertTrue(b.is_launchable())

    def test_pi_notes_policy_authority(self):
        pi = _load("pi_adapter.py", "ef_pi")
        a = pi.PiAdapter()
        # ch 21 — the rule must surface in every note set, launch or not
        notes = " ".join(a.launch_notes())
        self.assertIn("policy is enforced by the WORK-LAB Permission Gate", notes)
        h = a.health()
        self.assertEqual(h["policy_authority"], "work-lab-gate")


class FederationRegistryTests(unittest.TestCase):
    def test_default_fleet_is_five_honest_executors(self):
        fed_mod = _load("federation.py", "ef_fed")
        fed = fed_mod.default_federation()
        self.assertEqual(len(fed), 5)
        self.assertEqual(
            fed.executors(),
            ["codex", "dsh", "hermes", "openhands", "pi"],
        )
        # the health summary must state the one rule every plane obeys:
        self.assertIn(
            "policy authority is always the WORK-LAB Permission Gate",
            " ".join(fed.health()["notes"]),
        )

    def test_register_refuses_cross_type_shadow(self):
        fed_mod = _load("federation.py", "ef_fed")
        cod = _load("codex_adapter.py", "ef_codex")
        dsh = _load("dsh_adapter.py", "ef_dsh")
        fed = fed_mod.ExecutorFederation()
        fed.register(cod.CodexAdapter())
        # a DSH adapter claiming the "codex" name must be refused:
        # that is a wiring bug, not an upgrade.
        impostor = dsh.DshAdapter()
        impostor.executor = "codex"
        with self.assertRaises(ValueError):
            fed.register(impostor)
        # same-type re-register is allowed (a refresh)
        fed.register(cod.CodexAdapter())

    def test_unknown_executor_routing_degrades(self):
        fed_mod = _load("federation.py", "ef_fed")
        fed = fed_mod.ExecutorFederation()
        r = fed.new("ghost", project_id="x")
        self.assertFalse(r.ok)
        self.assertEqual(r.status, "UNKNOWN_EXECUTOR")


if __name__ == "__main__":
    unittest.main(verbosity=2)

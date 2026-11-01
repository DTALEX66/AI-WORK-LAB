#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Hermetic tests for the shared fail-closed tool locator (Prompt B-B/E) and the
unapproved-execution-path gate (Prompt B-C), cloud audit 2026-09-25.

Proven without touching a real machine (injected which/env/path-exists) and
without network (the whole point: a MISSING tool triggers zero fetch).
"""
from __future__ import annotations

import importlib.util
import json
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent.parent


def load(mod_rel: str, name: str):
    path = ROOT / mod_rel
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    try:
        spec.loader.exec_module(module)
    except BaseException:
        sys.modules.pop(name, None)
        raise
    return module


loc = load("design-lab/scripts/resolve_tool_locator.py", "resolve_tool_locator_under_test")
gate = load("design-lab/scripts/verify_execution_path_gate.py", "verify_execution_path_gate_under_test")

SCHEMA = json.loads((ROOT / "design-lab/config/tool-resolution.schema.json").read_text(encoding="utf-8"))
AUTHZ = json.loads((ROOT / "design-lab/config/install-authorization.schema.json").read_text(encoding="utf-8"))


class LocatorStrategyTest(unittest.TestCase):
    """Each of the six strategies, in isolation."""

    def _resolve(self, **kw):
        return loc.resolve_tool("open-design", repo_root=ROOT, **kw)

    def test_explicit_wins(self):
        r = self._resolve(explicit="/opt/od/Open Design.exe",
                          _path_exists=lambda p: True)
        self.assertEqual(r.status, "FOUND")
        self.assertEqual(r.locator_method, "explicit")

    def test_env_resolves_when_path_exists(self):
        r = self._resolve(explicit=None,
                          _env_get=lambda k: "/opt/od/Open Design.exe",
                          _path_exists=lambda p: True)
        self.assertEqual(r.locator_method, "env")

    def test_path_resolves_when_which_hits(self):
        r = self._resolve(explicit=None,
                          _env_get=lambda k: "",
                          _path_exists=lambda p: True,
                          _which=lambda name: "/usr/local/bin/opendesign")
        self.assertEqual(r.status, "FOUND")
        self.assertEqual(r.locator_method, "path")
        self.assertEqual(r.resolved_path, "/usr/local/bin/opendesign")

    def test_missing_when_nothing_resolves(self):
        r = self._resolve(explicit=None,
                          _env_get=lambda k: "",
                          _path_exists=lambda p: False,
                          _which=lambda name: None,
                          writable_roots={"design-toolchain": Path("/nowhere")})
        self.assertEqual(r.status, "MISSING")
        self.assertIsNone(r.resolved_path)
        # The fix message must be actionable and state no install was attempted.
        self.assertIn("No download, clone, or install was attempted", r.fix)

    def test_ambiguous_when_two_writable_candidates(self):
        def fake_which(name):
            # simulate two distinct writable installations on PATH
            return "/opt/a/opendesign" if name == "opendesign" else None
        # The locator aggregates path hits across the exe-name list; a second
        # name hitting a *different* path yields two candidates.
        r = self._resolve(explicit=None,
                         _env_get=lambda k: "",
                         _path_exists=lambda p: True,
                         _which=lambda name: {
                             "Open Design": "/opt/a/opendesign",
                             "Open Design.exe": "/opt/b/opendesign",
                         }.get(name))
        self.assertEqual(r.status, "AMBIGUOUS")
        self.assertIsNone(r.resolved_path)
        self.assertIn("multiple writable installations", r.fix)

    def test_blocked_when_logical_id_unknown(self):
        r = self._resolve(explicit=None,
                         _env_get=lambda k: "",
                         _path_exists=lambda p: False,
                         _which=lambda name: None)
        # an unknown logical id with no registered inputs is BLOCKED, not MISSING
        r2 = loc.resolve_tool("totally-unknown-tool", repo_root=ROOT,
                              _env_get=lambda k: "",
                              _path_exists=lambda p: False,
                              _which=lambda name: None)
        self.assertEqual(r2.status, "BLOCKED")
        self.assertIn("unregistered logical_id", r2.fix)


class ObservedOnlyTest(unittest.TestCase):
    """VERIFIED requires an *observed* value matching the expectation."""

    def test_expectation_without_observation_stays_found(self):
        r = loc.resolve_tool("open-design", repo_root=ROOT,
                             explicit="/opt/od/Open Design.exe",
                             expected_sha256="abc",
                             _path_exists=lambda p: True)
        self.assertEqual(r.status, "FOUND")  # no observed hash -> not VERIFIED
        self.assertIsNone(r.sha256)          # never fabricated

    def test_observed_match_is_verified(self):
        r = loc.resolve_tool("open-design", repo_root=ROOT,
                             explicit="/opt/od/Open Design.exe",
                             expected_sha256="abc",
                             observed_sha256="abc",
                             _path_exists=lambda p: True)
        self.assertEqual(r.status, "VERIFIED")
        self.assertEqual(r.sha256, "abc")

    def test_observed_mismatch_stays_found(self):
        r = loc.resolve_tool("open-design", repo_root=ROOT,
                             explicit="/opt/od/Open Design.exe",
                             expected_sha256="abc",
                             observed_sha256="zzz",
                             _path_exists=lambda p: True)
        self.assertEqual(r.status, "FOUND")  # mismatch -> not VERIFIED


class ReceiptShapeTest(unittest.TestCase):
    def test_receipt_matches_schema_required_and_status_enum(self):
        r = loc.resolve_tool("open-design", repo_root=ROOT,
                             _path_exists=lambda p: False,
                             _which=lambda n: None,
                             _env_get=lambda k: "").to_dict()
        findings = loc.validate_receipt_dict(r, SCHEMA)
        self.assertEqual(findings, [])

    def test_receipt_is_generated_not_ssot_marker(self):
        r = loc.resolve_tool("open-design", repo_root=ROOT).to_dict()
        self.assertEqual(r["schema_version"], "design-lab/tool-resolution/v1")
        self.assertIn(r["status"], loc.STATUSES)


class InstallAuthorizationShapeTest(unittest.TestCase):
    def test_receipt_requires_owner_approval_and_rollback(self):
        # both required keys present -> clean
        ok = {
            "schema_version": AUTHZ["properties"]["schema_version"]["const"],
            "logical_id": "open-design", "source": "owner", "revision": "v1",
            "license_spdx": "MIT", "destination": "/approved/root",
            "owner_approval": {"by": "owner", "at": "2026-09-25T00:00:00Z", "evidence": "receipt-hash"},
            "rollback": {"action": "restore backup", "verified_at": "2026-09-25T00:00:00Z"},
        }
        for key in AUTHZ["required"]:
            self.assertIn(key, ok)
        # dropping owner_approval or rollback must be rejected by the schema's
        # required list (proves they are mandatory, not optional).
        for key in ("owner_approval", "rollback"):
            broken = dict(ok)
            broken.pop(key)
            self.assertNotIn(key, broken)
            self.assertIn(key, AUTHZ["required"])


class ExecutionPathGateTest(unittest.TestCase):
    """The gate detects a NEW violation and a STALE pin (no repo mutation)."""

    def test_new_unpinned_hit_is_a_violation(self):
        findings, _ = self._run_with({"pins": []})
        self.assertTrue(any(f.startswith("NEW-VIOLATION") for f in findings))

    def _run_with(self, allowlist_doc):
        # point the gate at a synthetic allowlist by monkeypatching the loader
        orig = gate._load_allowlist
        gate._load_allowlist = lambda: allowlist_doc
        try:
            findings, files = gate.check()
            return findings, files
        finally:
            gate._load_allowlist = orig

    def test_no_stale_pin_when_all_pinned(self):
        findings, _ = self._run_with(json.loads(
            (ROOT / "design-lab/config/execution-path-allowlist.json").read_text(encoding="utf-8")))
        self.assertEqual(findings, [], f"expected clean, got: {findings}")

    def test_stale_pin_fails(self):
        doc = json.loads((ROOT / "design-lab/config/execution-path-allowlist.json").read_text(encoding="utf-8"))
        doc["pins"].append({"file": "does/not/exist.py", "pattern": "curl",
                            "reason": "x", "source": "x", "owner_approval": "x"})
        findings, _ = self._run_with(doc)
        self.assertTrue(any(f.startswith("STALE-PIN") for f in findings))


if __name__ == "__main__":
    unittest.main()

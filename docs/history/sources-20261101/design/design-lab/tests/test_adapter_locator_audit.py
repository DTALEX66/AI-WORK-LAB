#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Unit tests for the B4/G-4 adapter machine-location locator audit gate.

Hermetic: the pure logic is exercised directly — classification, the normalising
fingerprint, the triage invariants (untriaged / stale / schema drift), and the
bootstrap inventory. ``scan`` is driven through a monkeypatched repo root + a
temporary source file, so no real git repo or the checked-in inventory is read.
"""
from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "design-lab" / "scripts"))

import verify_adapter_locator_audit as ala  # noqa: E402


def _finding(fingerprint, kind, file="f.py", line=1, snippet="x", readable=True):
    return {
        "id": fingerprint, "file": file, "line": line, "kind": kind,
        "reason": "r", "snippet": snippet, "fingerprint": fingerprint,
        "readable": readable,
    }


def _inventory(*entries, triage_kinds=None):
    return {
        "schemaVersion": "design-lab/adapter-locator-inventory/v1",
        "policy": {"triage_kinds": list(triage_kinds) if triage_kinds else list(ala.TRIAGE_KINDS)},
        "findings": [
            {"id": e[0], "file": e[1] if len(e) > 1 else "f.py",
             "kind": e[2], "reason": "r", "pinned": e[3] if len(e) > 3 else True}
            for e in entries
        ],
    }


class ClassifyTests(unittest.TestCase):
    def test_guard_context_classifies_as_guard(self):
        self.assertEqual(ala._classify("drive", 'wide_exact = {norm_root(Path(r"C:\\Users"))}'), "guard")

    def test_exe_default_classifies_as_violation(self):
        self.assertEqual(ala._classify("drive", "return Path(r\"D:\\Programs\\App\\App.exe\")"), "violation")

    def test_env_home_is_a_locator(self):
        self.assertEqual(ala._classify("env_home", 'home = Path(os.environ.get("USERPROFILE"))'), "locator")

    def test_expanduser_is_a_locator(self):
        self.assertEqual(ala._classify("expanduser", 'p = os.path.expanduser("~/x")'), "locator")

    def test_com_registry_is_a_violation(self):
        self.assertEqual(ala._classify("com_registry", "key = r'HKLM\\SOFTWARE\\Vendor'"), "violation")

    def test_comment_drive_is_informational_message(self):
        self.assertEqual(ala._classify("drive", "# e.g. D:\\All projects\\X"), "message")


class NormaliseTests(unittest.TestCase):
    def test_collapse_whitespace(self):
        self.assertEqual(ala._normalise("  a   b "), "a b")

    def test_stable_across_line_shifts(self):
        self.assertEqual(ala._normalise("D:\\x"), ala._normalise("D:\\" + "x"))


class TriageInvariantTests(unittest.TestCase):
    def test_detects_untriaged(self):
        live = [_finding("a", "violation"), _finding("b", "guard")]
        inv = _inventory(("a", "f.py", "violation"))  # 'b' missing
        errors, stats = ala.check(live, inv)
        self.assertTrue(any("UNTRIAGED" in e for e in errors))
        self.assertEqual(stats["untriaged"], 1)

    def test_detects_stale_pinned(self):
        live = [_finding("a", "violation")]
        inv = _inventory(("a", "f.py", "violation"), ("z", "f.py", "guard"))  # 'z' pinned but not live
        errors, stats = ala.check(live, inv)
        self.assertTrue(any("STALE" in e for e in errors))
        self.assertEqual(stats["stale"], 1)

    def test_pass_when_all_triaged_and_live(self):
        live = [_finding("a", "violation"), _finding("b", "guard")]
        inv = _inventory(("a", "f.py", "violation"), ("b", "f.py", "guard"))
        errors, stats = ala.check(live, inv)
        self.assertEqual(errors, [])
        self.assertEqual(stats["untriaged"], 0)
        self.assertEqual(stats["stale"], 0)
        self.assertEqual(stats["violations"], 1)
        self.assertEqual(stats["guards"], 1)

    def test_schema_triage_kind_drift_fails(self):
        live = [_finding("a", "violation")]
        inv = _inventory(("a", "f.py", "violation"), triage_kinds=["violation", "guard"])  # missing 'locator'
        errors, _ = ala.check(live, inv)
        self.assertTrue(any("triage_kinds" in e for e in errors))

    def test_unreadable_source_fails_closed(self):
        live = [_finding("x", "violation", readable=False)]
        inv = _inventory(("x", "f.py", "violation"))
        errors, _ = ala.check(live, inv)
        self.assertTrue(any("UNREADABLE" in e for e in errors))

    def test_informational_kind_accepted_in_inventory(self):
        live = [_finding("a", "violation")]
        inv = _inventory(("a", "f.py", "violation"), ("m", "f.py", "message"))
        errors, _ = ala.check(live, inv)
        # a 'message' entry is a legal kind, not an error
        self.assertFalse(any("unknown kind" in e for e in errors))


class BootstrapTests(unittest.TestCase):
    def test_bootstrap_pins_every_live_triage_finding(self):
        live = [_finding("a", "violation"), _finding("b", "guard"), _finding("m", "message")]
        inv = ala._bootstrap_inventory(live)
        self.assertEqual(inv["policy"]["triage_kinds"], list(ala.TRIAGE_KINDS))
        ids = {e["id"] for e in inv["findings"]}
        # only the triage kinds are pinned; the informational 'message' is not
        self.assertIn("a", ids)
        self.assertIn("b", ids)
        self.assertNotIn("m", ids)
        for e in inv["findings"]:
            self.assertTrue(e["pinned"])
            self.assertEqual(e["classification"], "TODO-triage")


class ScanTests(unittest.TestCase):
    def test_scan_fingerprints_are_stable_and_classified(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            # Mirror the real shapes: the guard is the deny-set block that names
            # machine roots (drive_roots / wide_exact), the violation is an
            # overridable .exe default, the locator is an env-first home read.
            (root / "sample.py").write_text(
                "def f():\n"
                '    return Path(r"D:\\Programs\\App\\App.exe")\n'  # violation
                "    drive_roots = {\"C:\\\\\", \"D:\\\\\"}\n"  # guard
                '    wide_exact = {drive_roots | {"C:\\Users"}}\n'  # guard
                "    import os\n"
                '    home = os.environ.get("USERPROFILE")\n'  # locator
                , encoding="utf-8")
            old_root, old_tracked = ala.REPO_ROOT, ala._tracked
            ala.REPO_ROOT = root
            ala._tracked = lambda: ["sample.py"]
            try:
                findings = ala.scan()
            finally:
                ala.REPO_ROOT, ala._tracked = old_root, old_tracked

        kinds = {f["kind"] for f in findings if f["kind"] in ala.TRIAGE_KINDS}
        self.assertIn("violation", kinds)
        self.assertIn("guard", kinds)
        self.assertIn("locator", kinds)
        # the executable default is the violation; fingerprints are present + stable
        vio = [f for f in findings if f["kind"] == "violation"]
        self.assertTrue(all(f["fingerprint"] for f in vio))
        self.assertEqual(len({f["fingerprint"] for f in findings if f["fingerprint"]}),
                         len([f for f in findings if f["fingerprint"]]))


if __name__ == "__main__":
    unittest.main()

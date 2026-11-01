#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Hermetic unit tests for the shared Open Design fail-closed executable locator
(``design-lab/scripts/resolve_open_design_locator.py``), cloud audit 2026-09-25
Prompt B agent slice.

The tests monkeypatch the environment / ``shutil.which`` so they run identically
on any platform and prove the fail-closed invariants:

* an explicit value always wins;
* ``OPEN_DESIGN_EXE`` env beats PATH;
* PATH wins over fail-closed;
* when nothing resolves, ``path``/``method`` are None and *no* network, install,
  clone, or file write was performed (the resolver has no such code path at all,
  so a missing tool is a pure, side-effect-free error);
* the receipt is human-readable and names the checked locations.
"""
from __future__ import annotations

import os
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "design-lab" / "scripts"))

import resolve_open_design_locator as rol  # noqa: E402


class _EnvContext:
    """Temporarily set/remove env keys and restore them on exit (hermetic)."""
    def __init__(self, **kv):
        self.kv = kv
        self.saved = {}

    def __enter__(self):
        for k, v in self.kv.items():
            self.saved[k] = os.environ.get(k)
            if v is None:
                os.environ.pop(k, None)
            else:
                os.environ[k] = v
        return self

    def __exit__(self, *exc):
        for k, v in self.saved.items():
            if v is None:
                os.environ.pop(k, None)
            else:
                os.environ[k] = v
        return False


class ResolveOpenDesignExeTests(unittest.TestCase):
    def test_missing_tool_fails_closed_with_no_side_effects(self):
        with _EnvContext(OPEN_DESIGN_EXE=None):
            orig_which = rol.shutil.which
            rol.shutil.which = lambda name, *a, **k: None
            try:
                res = rol.resolve_open_design_exe(None)
            finally:
                rol.shutil.which = orig_which
        self.assertIsNone(res.path)
        self.assertIsNone(res.method)
        self.assertFalse(res.found)
        # it must record where it looked (an actionable, not silent, miss)
        self.assertTrue(any("OPEN_DESIGN_EXE" in c for c in res.checked))
        self.assertTrue(any("which" in c for c in res.checked))

    def test_explicit_value_wins_over_env_and_path(self):
        with _EnvContext(OPEN_DESIGN_EXE="/definitely/not/here.exe"):
            with tempfile.TemporaryDirectory() as td:
                target = Path(td) / "Open Design.exe"
                target.write_text("x", encoding="utf-8")
                res = rol.resolve_open_design_exe(str(target))
                self.assertEqual(res.method, "explicit")
                self.assertEqual(res.path, target)
                self.assertTrue(res.found)

    def test_env_beats_path(self):
        with _EnvContext(OPEN_DESIGN_EXE=str(self._make_exe())):
            res = rol.resolve_open_design_exe(None)
            self.assertEqual(res.method, "env")
            self.assertTrue(res.found)

    def test_env_absent_but_path_hit_resolves(self):
        with _EnvContext(OPEN_DESIGN_EXE=None):
            with tempfile.TemporaryDirectory() as td:
                found = Path(td) / "Open Design.exe"
                found.write_text("x", encoding="utf-8")
                orig_which = rol.shutil.which
                rol.shutil.which = lambda name, *a, **k: str(found) if name in ("Open Design", "Open Design.exe") else None
                try:
                    res = rol.resolve_open_design_exe(None)
                finally:
                    rol.shutil.which = orig_which
                self.assertEqual(res.method, "path")
                self.assertEqual(res.path, found)

    def test_explicit_missing_path_is_unresolved_not_crash(self):
        res = rol.resolve_open_design_exe("/this/does/not/exist.exe")
        self.assertIsNone(res.path)
        self.assertIsNone(res.method)

    def test_receipt_names_checked_locations_on_miss(self):
        with _EnvContext(OPEN_DESIGN_EXE=None):
            orig_which = rol.shutil.which
            rol.shutil.which = lambda name, *a, **k: None
            try:
                receipt = rol.resolver_receipt(None)
            finally:
                rol.shutil.which = orig_which
        self.assertIn("OPEN_DESIGN_EXE_UNRESOLVED", receipt)
        self.assertIn("no download or install", receipt)

    def _make_exe(self) -> Path:
        d = tempfile.mkdtemp(prefix="od-test-")
        p = Path(d) / "Open Design.exe"
        p.write_text("x", encoding="utf-8")
        return p


if __name__ == "__main__":
    unittest.main()

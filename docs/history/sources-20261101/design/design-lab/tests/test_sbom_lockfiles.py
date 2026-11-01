#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Unit tests for SBOM lockfile-level bindings (DL-CLOUDAUDIT-B2 / G-2).

Covers the pnpm/uv/requirements parsers and the fail-closed integrity check
in design-lab/scripts/verify_sbom.py. Hermetic: every lockfile is constructed
in a temp dir and written byte-safe (write_bytes) so no real lockfile is ever
mutated and no CRLF round-trip can pollute a digest.
"""
from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "design-lab" / "scripts"))

import verify_sbom  # noqa: E402
from verify_sbom import (  # noqa: E402
    _parse_pnpm_lock,
    _parse_uv_lock,
    _requirement_pins,
    _verify_lockfile_bindings,
    build_lockfile_bindings,
)

PNPM = """lockfileVersion: '9.0'

settings:
  autoInstallPeers: true

importers:
  .:
    dependencies:
      alpha:
        specifier: ^1.0.0
        version: 1.0.0

packages:

  alpha@1.0.0:
    resolution: {integrity: sha512-AAAaaabbbb1111CCCCddddd2222==}
    engines: {node: '>=18'}

  beta@2.0.0:
    resolution: {integrity: sha512-BBBbbbbbcccc3333DDDDdddd4444==}
    optional: true

snapshots:

  alpha@1.0.0:
    dependencies:
      beta: 2.0.0

  beta@2.0.0: {}

  zeta@9.9.9: {}
"""

UV = """version = 1
revision = 1
requires-python = ">=3.11"

[[package]]
name = "alpha"
version = "1.0.0"
source = "registry https://pypi.org/simple"
sdist = { url = "https://example.invalid/alpha-1.0.0.tar.gz", hash = "sha256:aaaa" }

[[package]]
name = "beta"
version = "2.0.0"
source = "registry https://pypi.org/simple"
wheels = [
    { url = "https://example.invalid/beta-2.0.0-py3-none-any.whl", hash = "sha256:bbbb" },
]
"""

REQS = "-r requirements-dev.txt\nalpha==1.0.0\nbeta==2.0.0\n# a comment\n"
REQS_DEV = "gamma==3.0.0\n"


def _write(root: Path, name: str, text: str) -> None:
    (root / name).write_bytes(text.encode("utf-8"))


class PnpmParseTests(unittest.TestCase):
    def test_scoped_to_packages_section_only(self):
        parsed = _parse_pnpm_lock(PNPM)
        entries = parsed["entries"]
        # packages section has exactly alpha + beta; zeta exists ONLY in
        # snapshots and must not leak in.
        self.assertEqual(set(entries), {"alpha@1.0.0", "beta@2.0.0"})
        self.assertNotIn("zeta@9.9.9", entries)

    def test_digests_captured_not_overwritten(self):
        entries = _parse_pnpm_lock(PNPM)["entries"]
        # The regression this guards: parsing to EOF let the snapshots section
        # (same keys, no resolution.integrity) overwrite every digest to None.
        self.assertEqual(
            entries["alpha@1.0.0"]["integrity"], "sha512-AAAaaabbbb1111CCCCddddd2222==")
        self.assertEqual(
            entries["beta@2.0.0"]["integrity"], "sha512-BBBbbbbbcccc3333DDDDdddd4444==")
        self.assertTrue(entries["beta@2.0.0"]["optional"])
        self.assertFalse(entries["alpha@1.0.0"]["optional"])

    def test_version_split_and_peer_suffix(self):
        # Real pnpm keys carrying a peer suffix are single-quoted; the parser
        # strips the quotes and the trailing peer group, then splits
        # name@version on the last '@'.
        text = ("lockfileVersion: '9.0'\n\npackages:\n\n"
                "  'alpha@1.0.0(peer@2.0.0)':\n"
                "    resolution: {integrity: sha512-XXX}\n")
        e = _parse_pnpm_lock(text)["entries"]
        key = "alpha@1.0.0(peer@2.0.0)"
        self.assertIn(key, e)
        self.assertEqual(e[key]["name"], "alpha")
        self.assertEqual(e[key]["version"], "1.0.0")
        self.assertEqual(e[key]["integrity"], "sha512-XXX")


class UvParseTests(unittest.TestCase):
    def test_structure(self):
        parsed = _parse_uv_lock(UV)
        self.assertEqual(parsed["packageCount"], 2)
        pk = parsed["packages"]
        self.assertEqual(set(pk), {"alpha@1.0.0", "beta@2.0.0"})
        self.assertEqual(pk["alpha@1.0.0"]["sdist"], "sha256:aaaa")
        self.assertEqual(pk["beta@2.0.0"]["wheels"], ["sha256:bbbb"])

    def test_meta_only_package_has_no_digests(self):
        text = ("version = 1\n\n[[package]]\nname = \"proj\"\nversion = \"0.1.0a0\"\n"
                "source = \"virtual .\"\n")
        pk = _parse_uv_lock(text)["packages"]
        self.assertIsNone(pk["proj@0.1.0a0"]["sdist"])
        self.assertEqual(pk["proj@0.1.0a0"]["wheels"], [])


class RequirementPinsTests(unittest.TestCase):
    def test_resolves_top_level_includes(self):
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            _write(root, "requirements.txt", REQS)
            _write(root, "requirements-dev.txt", REQS_DEV)
            pins = _requirement_pins(root, (root / "requirements.txt").read_text(encoding="utf-8"))
            self.assertEqual(pins, ["gamma==3.0.0", "alpha==1.0.0", "beta==2.0.0"])

    def test_missing_include_skipped_not_fatal(self):
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            text = "-r does-not-exist.txt\nalpha==1.0.0\n"
            self.assertEqual(_requirement_pins(root, text), ["alpha==1.0.0"])


class BindingVerifyTests(unittest.TestCase):
    def _make_repo(self, d: str) -> Path:
        root = Path(d)
        _write(root, "pnpm-lock.yaml", PNPM)
        _write(root, "uv.lock", UV)
        _write(root, "requirements.txt", REQS)
        _write(root, "requirements-dev.txt", REQS_DEV)
        return root

    def test_build_then_verify_clean(self):
        with tempfile.TemporaryDirectory() as d:
            root = self._make_repo(d)
            binding = build_lockfile_bindings(root)
            sbom = {"lockfileBindings": binding}
            self.assertEqual(_verify_lockfile_bindings(sbom, root), [])

    def test_missing_bindings_fail_closed(self):
        with tempfile.TemporaryDirectory() as d:
            root = self._make_repo(d)
            finding = _verify_lockfile_bindings({}, root)
            self.assertEqual(len(finding), 1)
            self.assertIn("missing lockfileBindings", finding[0])

    def test_lockfile_sha_mismatch_caught(self):
        with tempfile.TemporaryDirectory() as d:
            root = self._make_repo(d)
            sbom = {"lockfileBindings": build_lockfile_bindings(root)}
            # byte-safe tamper: append one line -> sha256 changes
            p = root / "pnpm-lock.yaml"
            p.write_bytes(p.read_bytes() + b"# tamper\n")
            findings = _verify_lockfile_bindings(sbom, root)
            self.assertTrue(
                any("pnpm-lock.yaml changed since SBOM" in f for f in findings),
                findings)

    def test_pnpm_manifest_drift_caught(self):
        with tempfile.TemporaryDirectory() as d:
            root = self._make_repo(d)
            sbom = {"lockfileBindings": build_lockfile_bindings(root)}
            # sha still matches on-disk; bound manifest loses an entry -> drift
            del sbom["lockfileBindings"]["pnpm-lock.yaml"]["manifest"]["beta@2.0.0"]
            findings = _verify_lockfile_bindings(sbom, root)
            self.assertTrue(
                any("pnpm manifest drift" in f for f in findings), findings)

    def test_uv_manifest_drift_caught(self):
        with tempfile.TemporaryDirectory() as d:
            root = self._make_repo(d)
            sbom = {"lockfileBindings": build_lockfile_bindings(root)}
            sbom["lockfileBindings"]["uv.lock"]["manifest"]["alpha@1.0.0"]["sdist"] = "sha256:TAMPERED"
            findings = _verify_lockfile_bindings(sbom, root)
            self.assertTrue(
                any("uv.lock manifest drift" in f for f in findings), findings)

    def test_requirements_pins_drift_caught(self):
        with tempfile.TemporaryDirectory() as d:
            root = self._make_repo(d)
            sbom = {"lockfileBindings": build_lockfile_bindings(root)}
            sbom["lockfileBindings"]["requirements.txt"]["pins"].append("evil==9.9.9")
            findings = _verify_lockfile_bindings(sbom, root)
            self.assertTrue(
                any("requirements pins drift" in f for f in findings), findings)

    def test_bound_integrity_count_matches_ground_truth(self):
        with tempfile.TemporaryDirectory() as d:
            root = self._make_repo(d)
            binding = build_lockfile_bindings(root)
            pn = binding["pnpm-lock.yaml"]
            self.assertEqual(pn["entryCount"], 2)
            self.assertEqual(pn["integrityCount"], 2)


if __name__ == "__main__":
    unittest.main(verbosity=2)

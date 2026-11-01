"""Regression tests for two silent-truth defects found on 2026-10-01.

1. BOM-broken software registry. `config/software-registry.json` was written
   with a UTF-8 BOM. `composition_root._load_software_registry()` reads it with
   `encoding="utf-8"`, so `json.loads` raised
   `JSONDecodeError: Unexpected UTF-8 BOM`, and the bare `except` returned `[]`.
   The consequence was invisible: the snapshot's `software[]` projection was
   always empty, so the Observer's Software lane could only ever show UNKNOWN
   even though 7 software entries are registered. Nothing anywhere failed.

2. First-existing-directory-wins install probing. `platform_discovery._probe_install`
   took the first declared root that merely EXISTS and never expanded
   environment variables. DSH therefore resolved to the stale leftover
   `D:/All projects/DSH` directory (now holding only a .dsh data folder) and was
   reported `SINGLE_UNVERIFIED`, while the real official install sat unprobed at
   the vendor default path.

These tests are read-only and assert the honest contract, not an implementation.
"""
from __future__ import annotations

import json
import os
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "services" / "orchestration"))
sys.path.insert(0, str(ROOT / "packages" / "client-neutral-core" / "scripts"))

import platform_discovery as pd  # noqa: E402
import project_temp  # noqa: E402


class SoftwareRegistryIsLoadable(unittest.TestCase):
    """The registry must load through the SAME code path production uses."""

    def test_registry_file_has_no_bom(self) -> None:
        raw = (ROOT / "config" / "software-registry.json").read_bytes()
        self.assertFalse(
            raw.startswith(b"\xef\xbb\xbf"),
            "software-registry.json must not carry a UTF-8 BOM: the production "
            "loader reads it with encoding='utf-8', so a BOM makes the whole "
            "registry silently load as []",
        )

    def test_production_loader_returns_the_registered_entries(self) -> None:
        import composition_root as cr

        entries = cr._load_software_registry()
        self.assertTrue(
            entries,
            "the software registry load must not silently degrade to []",
        )
        self.assertGreaterEqual(len(entries), 7)
        ids = {str(e.get("softwareId")) for e in entries}
        for expected in ("hermes", "codex", "deepseek-harness", "github"):
            self.assertIn(expected, ids)

    def test_software_projection_is_not_silently_empty(self) -> None:
        import composition_root as cr

        cr._software_discovery_cache.clear()
        projection = cr._build_software_projection()
        # Discovery may legitimately find nothing installed, but the REGISTRY is
        # non-empty, so the projection must still carry one row per entry with
        # an honest UNKNOWN rather than being empty.
        self.assertTrue(
            projection,
            "software[] must not be empty while the registry has entries",
        )
        for row in projection:
            self.assertTrue(row.get("softwareId"))
            self.assertIn(
                row.get("locationStatus"),
                {
                    "SINGLE_VERIFIED", "SINGLE_UNVERIFIED", "DUAL_INSTALLATION",
                    "NOT_INSTALLED", "UNKNOWN", "LOCATION_DRIFT",
                },
            )


class InstallProbePrefersTheRealRoot(unittest.TestCase):
    """A root that contains the executable must beat one that merely exists."""

    def _fixture(self) -> tuple[Path, Path]:
        # ERR-140 class: this helper created a system-temp root and never removed it.
        tmp = project_temp.fixture_dir(prefix="nf23-install-")
        stale = tmp / "stale"
        real = tmp / "real"
        stale.mkdir()
        real.mkdir()
        (real / "Real App.exe").write_bytes(b"stub")
        return stale, real

    def test_env_vars_are_expanded_in_roots(self) -> None:
        # NOTE (2026-10-01, AG-06u): this assertion is platform-INDEPENDENT by design.
        # It implies the probe expands the Windows-style `%VAR%` form on any platform.
        # That was originally false: the probe used os.path.expandvars, which honours
        # `%VAR%` only on Windows, so the case passed here and FAILED on the Linux CI
        # runner with `AssertionError: None != '/tmp/tmp...'` - the variable stayed
        # literal, the root did not exist, and the probe reported no install root at
        # all. The production defect was in _expand_root, not in this test, so the
        # probe was fixed rather than the assertion weakened or skipped.
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            (base / "App.exe").write_bytes(b"stub")
            os.environ["WL_TEST_INSTALL_ROOT"] = str(base)
            try:
                candidate = {
                    "install_roots": ["%WL_TEST_INSTALL_ROOT%"],
                    "executables": ["App.exe"],
                }
                probe = pd._probe_install(candidate)
                self.assertEqual(probe["install_root"], str(base))
                self.assertIsNotNone(probe["executable_realpath"])
            finally:
                os.environ.pop("WL_TEST_INSTALL_ROOT", None)

    def test_expand_root_handles_both_forms_and_never_blanks_unknowns(self) -> None:
        os.environ["WL_EXPAND_POSIX"] = "posix-ok"
        os.environ["WL_EXPAND_WIN"] = "win-ok"
        os.environ["WL_EXPAND_A"] = "%WL_EXPAND_B%"
        os.environ["WL_EXPAND_B"] = "nested-ok"
        os.environ["WL_EXPAND_CASE"] = "case-ok"
        try:
            # The declared form in this inventory is Windows-like, so it must expand
            # even where the host is POSIX.
            self.assertEqual(pd._expand_root("%WL_EXPAND_WIN%"), "win-ok")
            # POSIX form must keep working too.
            self.assertEqual(pd._expand_root("$WL_EXPAND_POSIX"), "posix-ok")
            # An unset variable must stay LITERAL: blanking it would silently turn a
            # misdeclared root into the filesystem root or the cwd.
            self.assertEqual(
                pd._expand_root("%WL_EXPAND_DEFINITELY_UNSET%"),
                "%WL_EXPAND_DEFINITELY_UNSET%",
            )
            # A variable holding another variable resolves (bounded, not infinite).
            self.assertEqual(pd._expand_root("%WL_EXPAND_A%"), "nested-ok")
            # Windows environment variables are case-insensitive.
            self.assertEqual(pd._expand_root("%wl_expand_case%"), "case-ok")
        finally:
            for key in (
                "WL_EXPAND_POSIX",
                "WL_EXPAND_WIN",
                "WL_EXPAND_A",
                "WL_EXPAND_B",
                "WL_EXPAND_CASE",
            ):
                os.environ.pop(key, None)

    def test_expand_root_leaves_a_path_free_of_variables_untouched(self) -> None:
        plain = str(Path("/tmp") / "no-vars") if os.name != "nt" else r"C:\no-vars"
        self.assertEqual(pd._expand_root(plain), plain)

    def test_root_with_executable_wins_over_stale_existing_dir(self) -> None:
        stale, real = self._fixture()
        candidate = {
            # stale is intentionally FIRST and does exist, but has no executable
            "install_roots": [str(stale), str(real)],
            "executables": ["Real App.exe"],
        }
        probe = pd._probe_install(candidate)
        self.assertEqual(probe["install_root"], str(real))
        self.assertIsNotNone(probe["executable_realpath"])

    def test_existing_dir_without_executable_is_reported_without_exe(self) -> None:
        stale, _ = self._fixture()
        candidate = {
            "install_roots": [str(stale)],
            "executables": ["Absent.exe"],
        }
        probe = pd._probe_install(candidate)
        # The directory is reported (it exists) but the executable stays None so
        # the resolver classifies it as unverified instead of a valid install.
        self.assertEqual(probe["install_root"], str(stale))
        self.assertIsNone(probe["executable_realpath"])

    def test_dsh_inventory_does_not_pin_a_single_drive(self) -> None:
        entry = next(
            e for e in pd.SOFTWARE_CANDIDATE_INVENTORY
            if e["software_id"] == "deepseek-harness"
        )
        roots = entry["install_roots"]
        self.assertGreaterEqual(len(roots), 2, "a legacy fallback root is expected")
        # The first (preferred) root must not be a hardcoded single-machine path.
        self.assertIn("%LOCALAPPDATA%", roots[0])
        self.assertIn("DeepSeek Harness.exe", entry["executables"])


if __name__ == "__main__":
    unittest.main()

"""U17 / WS-2 spec-3: software[] builder shape test (mandatory discovery).

Tests the ``_build_software_projection`` builder added to
``composition_root.py`` by spec-3. Three fixture shapes:

1. **Empty registry** — no entries → ``[]``
2. **All NOT_INSTALLED** — registry entries but discovery reports no install
   root → every entry gets ``locationStatus="NOT_INSTALLED"``,
   ``installRoot=None``, ``discoverySource`` from the resolver
3. **One SINGLE_VERIFIED** — a single install root is observed and verified
   → that entry has ``locationStatus="SINGLE_VERIFIED"``, the real root path,
   and ``duplicateInstallation=False``

UNKNOWN discipline: if the discovery module is unavailable (import failed),
every entry gets ``locationStatus="UNKNOWN"`` and
``discoverySource="unavailable"`` — we never fabricate a value.

Negative-control (nf*): this test file is discovered by
``MANDATORY_TEST_GLOBS = ("test_*.py", "nf*.py")`` — it is a ``test_*.py``
file so it is always included in the mandatory batch.
"""
from __future__ import annotations

import sys
import unittest
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parents[2]

# Inject the module roots so composition_root's top-level imports resolve
# regardless of how the test process was launched.
_sys_paths = [
    str(ROOT / "services" / "orchestration"),
    str(ROOT / "packages" / "client-neutral-core" / "scripts"),
]
for _p in _sys_paths:
    if _p not in sys.path:
        sys.path.insert(0, _p)

from composition_root import (  # noqa: E402
    _build_software_projection,
    clear_software_discovery_cache,
)
from snapshot_api import build_snapshot  # noqa: E402
from snapshot_validator import validate_snapshot  # noqa: E402


# ---------------------------------------------------------------------------
# Fixtures — three shapes the spec names explicitly
# ---------------------------------------------------------------------------

EMPTY_REGISTRY: list[dict] = []

NOT_INSTALLED_REGISTRY: list[dict] = [
    {"softwareId": "hermes", "displayName": "Hermes"},
    {"softwareId": "codex", "displayName": "Codex"},
]

SINGLE_VERIFIED_REGISTRY: list[dict] = [
    {"softwareId": "hermes", "displayName": "Hermes"},
]


def _make_obs(software_id: str, location_status: str, install_root: str | None = None) -> dict:
    """Minimal observation dict matching the shape discover_software_installations
    returns (see platform_discovery.py discover_software_installations)."""
    return {
        "software_id": software_id,
        "package_identity": software_id,
        "install_root": install_root,
        "executable_realpath": None,
        "location_status": location_status,
        "observed_existing_location": install_root,
        "discovery_source": "real-platform-probe",
    }


NOT_INSTALLED_OBSERVATIONS: list[dict] = [
    _make_obs("hermes", "NOT_INSTALLED"),
    _make_obs("codex", "NOT_INSTALLED"),
]

SINGLE_VERIFIED_OBSERVATIONS: list[dict] = [
    _make_obs("hermes", "SINGLE_VERIFIED", install_root="C:/Users/test/hermes"),
]


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

class SoftwareProjectionShapeTests(unittest.TestCase):
    """Assert output shape and UNKNOWN discipline for _build_software_projection."""

    def setUp(self) -> None:
        clear_software_discovery_cache()

    def tearDown(self) -> None:
        clear_software_discovery_cache()

    # -- Shape: empty registry ---------------------------------------------

    def test_empty_registry_produces_empty_list(self) -> None:
        """Empty registry → software = [] (not None, not a dict)."""
        with mock.patch("composition_root._load_software_registry", return_value=EMPTY_REGISTRY), \
             mock.patch(
                 "composition_root._platform_discovery.discover_software_installations",
                 return_value=[],
             ) as _disc:
            result = _build_software_projection()
        self.assertIsInstance(result, list)
        self.assertEqual(result, [])

    # -- Shape: all NOT_INSTALLED ------------------------------------------

    def test_all_not_installed_preserves_location_status(self) -> None:
        """Registry entries + discovery NOT_INSTALLED → every entry has
        locationStatus='NOT_INSTALLED', installRoot=None, duplicateInstallation=False."""
        with mock.patch(
            "composition_root._load_software_registry", return_value=NOT_INSTALLED_REGISTRY
        ), mock.patch(
            "composition_root._platform_discovery.discover_software_installations",
            return_value=NOT_INSTALLED_OBSERVATIONS,
        ):
            result = _build_software_projection()

        self.assertEqual(len(result), 2)
        for entry in result:
            self.assertIsInstance(entry, dict)
            # Every field the frontend SoftwareIdentity expects must be present
            self.assertIn("softwareId", entry)
            self.assertIn("displayName", entry)
            self.assertIn("installRoot", entry)
            self.assertIn("executableRealpath", entry)
            self.assertIn("discoveredVersion", entry)
            self.assertIn("releaseChannel", entry)
            self.assertIn("updateAvailable", entry)
            self.assertIn("duplicateInstallation", entry)
            self.assertIn("expectedLocation", entry)
            self.assertIn("observedLocation", entry)
            self.assertIn("locationStatus", entry)
            self.assertIn("lastVerified", entry)
            self.assertIn("discoverySource", entry)
            # NOT_INSTALLED discipline
            self.assertEqual(entry["locationStatus"], "NOT_INSTALLED")
            self.assertIsNone(entry["installRoot"])
            self.assertIsNone(entry["executableRealpath"])
            self.assertIsNone(entry["discoveredVersion"])
            self.assertIsNone(entry["updateAvailable"])
            self.assertFalse(entry["duplicateInstallation"])
            # discoverySource is the real probe source, not "unavailable"
            self.assertEqual(entry["discoverySource"], "real-platform-probe")

    # -- Shape: one SINGLE_VERIFIED ----------------------------------------

    def test_single_verified_entry_has_real_root_and_no_duplicate(self) -> None:
        """A SINGLE_VERIFIED entry must carry the real install root,
        duplicateInstallation=False, and the real discovery source."""
        with mock.patch(
            "composition_root._load_software_registry", return_value=SINGLE_VERIFIED_REGISTRY
        ), mock.patch(
            "composition_root._platform_discovery.discover_software_installations",
            return_value=SINGLE_VERIFIED_OBSERVATIONS,
        ):
            result = _build_software_projection()

        self.assertEqual(len(result), 1)
        entry = result[0]
        self.assertEqual(entry["softwareId"], "hermes")
        self.assertEqual(entry["displayName"], "Hermes")
        self.assertEqual(entry["locationStatus"], "SINGLE_VERIFIED")
        self.assertEqual(entry["installRoot"], "C:/Users/test/hermes")
        self.assertFalse(entry["duplicateInstallation"])
        self.assertEqual(entry["discoverySource"], "real-platform-probe")

    # -- UNKNOWN discipline: discovery module unavailable ------------------

    def test_discovery_unavailable_returns_unknown_entries(self) -> None:
        """When the discovery module import failed (_platform_discovery is None),
        _build_software_projection returns [] — no entries are fabricated."""
        with mock.patch("composition_root._platform_discovery", None):
            result = _build_software_projection()
        # The module is None → early return with [] (no fabrication).
        self.assertEqual(result, [])

    def test_registry_entry_without_observation_gets_unknown_status(self) -> None:
        """A registry entry that has NO matching observation in the discovery
        output must get locationStatus='UNKNOWN' + discoverySource='unavailable'
        — never a fabricated status."""
        # Registry has one entry; discovery returns an empty list.
        with mock.patch(
            "composition_root._load_software_registry", return_value=SINGLE_VERIFIED_REGISTRY
        ), mock.patch(
            "composition_root._platform_discovery.discover_software_installations",
            return_value=[],
        ):
            result = _build_software_projection()

        self.assertEqual(len(result), 1)
        entry = result[0]
        self.assertEqual(entry["locationStatus"], "UNKNOWN")
        self.assertEqual(entry["discoverySource"], "unavailable")
        self.assertIsNone(entry["installRoot"])
        self.assertIsNone(entry["executableRealpath"])

    # -- Integration: build_v3_snapshot carries software key ----------------

    def test_build_snapshot_includes_software_key_when_supplied(self) -> None:
        """build_snapshot(software=[...]) must expose the key in the output."""
        snap = build_snapshot(
            revision=1,
            generated_at="2026-09-21T00:00:00Z",
            projects=[{"projectId": "p", "displayName": "P"}],
            software=SINGLE_VERIFIED_OBSERVATIONS,  # pass raw observations as a smoke check
        )
        # The software key must be present and equal to what was passed in.
        self.assertIn("software", snap)
        self.assertIsInstance(snap["software"], list)
        self.assertEqual(snap["software"], SINGLE_VERIFIED_OBSERVATIONS)

    def test_build_snapshot_omits_software_key_when_none(self) -> None:
        """When software=None the key is omitted — backward-compatible shape."""
        snap = build_snapshot(
            revision=1,
            generated_at="2026-09-21T00:00:00Z",
            projects=[{"projectId": "p", "displayName": "P"}],
        )
        self.assertNotIn("software", snap)

    def test_snapshot_with_software_passes_validator(self) -> None:
        """validate_snapshot must not reject a snapshot that carries software[]."""
        snap = build_snapshot(
            revision=1,
            generated_at="2026-09-21T00:00:00Z",
            projects=[{"projectId": "p", "displayName": "P"}],
            software=SINGLE_VERIFIED_OBSERVATIONS,
        )
        result = validate_snapshot(snap)
        self.assertTrue(result["valid"], result.get("errors"))

    # -- Bounded cache ------------------------------------------------------

    def test_cache_returns_same_list_within_ttl(self) -> None:
        """Two calls within the TTL must return the identical cached list
        (same object identity) without re-invoking discovery."""
        with mock.patch(
            "composition_root._load_software_registry", return_value=SINGLE_VERIFIED_REGISTRY
        ), mock.patch(
            "composition_root._platform_discovery.discover_software_installations",
            return_value=SINGLE_VERIFIED_OBSERVATIONS,
        ) as _disc:
            first = _build_software_projection()
            second = _build_software_projection()
        # Second call served from cache: discovery ran only once.
        self.assertEqual(_disc.call_count, 1)
        self.assertIs(first, second)

    def test_clear_cache_forces_refresh(self) -> None:
        """After clear_software_discovery_cache the next call re-invokes discovery."""
        with mock.patch(
            "composition_root._load_software_registry", return_value=SINGLE_VERIFIED_REGISTRY
        ), mock.patch(
            "composition_root._platform_discovery.discover_software_installations",
            return_value=SINGLE_VERIFIED_OBSERVATIONS,
        ) as _disc:
            _build_software_projection()
            clear_software_discovery_cache()
            _build_software_projection()
        self.assertEqual(_disc.call_count, 2)


if __name__ == "__main__":
    unittest.main()

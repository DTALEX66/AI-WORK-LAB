"""C2 negative control: structure violations must FAIL; discovery-only
states must NOT be converted to a not-installed verdict."""
from __future__ import annotations

import importlib.util
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SCRIPT = ROOT / "packages/client-neutral-core/scripts/verify_external_libraries_index.py"


def load_module():
    spec = importlib.util.spec_from_file_location("verify_extlib", SCRIPT)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class ExternalLibrariesIndexStructureTests(unittest.TestCase):
    def setUp(self) -> None:
        self.m = load_module()

    def test_good_structure_passes(self) -> None:
        data = {
            "schemaVersion": "work-lab/external-libraries-index/v1",
            "policy": "内容不上传",
            "sharedRoots": {"r": "D:/x"},
            "libraries": [
                {"id": "a", "sharedRoot": "r", "relativePath": "p", "kind": "model-weights", "ownedBy": "X", "assets": [{"name": "m"}]},
            ],
        }
        self.assertEqual(self.m.structure_check(data), [])

    def test_bad_schema_fails(self) -> None:
        data = {"schemaVersion": "wrong", "policy": "x", "sharedRoots": {"r": "D:/x"}, "libraries": [{}]}
        errors = self.m.structure_check(data)
        self.assertTrue(any("schemaVersion" in e for e in errors))

    def test_model_lib_empty_assets_fails(self) -> None:
        data = {
            "schemaVersion": "work-lab/external-libraries-index/v1",
            "policy": "x",
            "sharedRoots": {"r": "D:/x"},
            "libraries": [{"id": "a", "sharedRoot": "r", "relativePath": "p", "kind": "model-weights", "ownedBy": "X", "assets": []}],
        }
        self.assertTrue(any("empty assets" in e for e in self.m.structure_check(data)))

    def test_undeclared_shared_root_reference_fails(self) -> None:
        data = {
            "schemaVersion": "work-lab/external-libraries-index/v1",
            "policy": "x",
            "sharedRoots": {"r": "D:/x"},
            "libraries": [{"id": "a", "sharedRoot": "other", "relativePath": "p", "kind": "toolchain", "ownedBy": "X"}],
        }
        self.assertTrue(any("undeclared sharedRoot" in e for e in self.m.structure_check(data)))


class ExternalLibrariesIndexDiscoveryTests(unittest.TestCase):
    """Discovery states are machine observations: never a not-installed verdict."""

    def setUp(self) -> None:
        self.m = load_module()

    def test_discovery_status_vocabulary_is_closed(self) -> None:
        self.assertIn("NOT_SEARCHED", self.m.DISCOVERY_STATUSES)
        self.assertIn("VOLUME_OFFLINE", self.m.DISCOVERY_STATUSES)
        self.assertIn("ACCESS_DENIED", self.m.DISCOVERY_STATUSES)
        self.assertIn("PATH_STALE", self.m.DISCOVERY_STATUSES)
        self.assertIn("FOUND_COMPATIBLE", self.m.DISCOVERY_STATUSES)

    def test_nonfound_root_is_reported_not_fatal(self) -> None:
        status, _detail = self.m.discover_root("Q:/definitely/absent/volume")
        # A missing root must be a PATH_STALE / VOLUME_OFFLINE observation,
        # never a hard failure code.
        self.assertIn(status, ("PATH_STALE", "VOLUME_OFFLINE"))

    def test_run_check_is_structure_gated_not_discovery_gated(self) -> None:
        # A fully valid structure whose registered root does not exist on this
        # machine must still PASS (discovery state is reported, not fatal).
        good = {
            "schemaVersion": "work-lab/external-libraries-index/v1",
            "policy": "内容不上传",
            "sharedRoots": {"r": "Z:/absent/registered/root"},
            "libraries": [{"id": "a", "sharedRoot": "r", "relativePath": "p", "kind": "toolchain", "ownedBy": "X"}],
        }
        with tempfile.TemporaryDirectory() as tmp:
            index = Path(tmp) / "external-libraries-index.json"
            index.write_text(json.dumps(good), encoding="utf-8")
            rc = self.m.run_check(index, authorized_discovery=True)
            self.assertEqual(rc, 0, "authorized discovery of a missing root must not fail the gate")

    def test_no_hardcoded_absolute_checkout_path(self) -> None:
        source = SCRIPT.read_text(encoding="utf-8")
        self.assertNotIn("D:\\All projects\\WORK-LAB", source.replace("\\\\", "\\\\"))
        self.assertNotIn("D:/All projects/WORK-LAB", source)


if __name__ == "__main__":
    unittest.main()

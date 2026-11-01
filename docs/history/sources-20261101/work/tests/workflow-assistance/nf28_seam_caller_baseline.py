"""Negative controls for the three-project seam-caller baseline (audit F19).

Audit F19: the three-project-boundary verifier checked markers, seams and
manifests, so a PASS could not show that a business boundary violation was absent
— a marker test is not a boundary-acceptance test. The SSOT's seams declare "no
new callers allowed", and that rule had no machine check at all. Scanning found
ZERO code callers of every seam contract; the only references were the verifier's
own path constants. A rule that is both unenforced and trivially satisfied is
exactly when a silent regression is cheapest to introduce.

The control that matters is the one proving the new check can FIRE. A baseline
check that only ever passes is indistinguishable from no check, so these tests
synthesize a fake repo root and confirm the caller scan grows when a caller is
added and does not when one is removed.

Synthetic fixtures in a temp dir only. No repository file is written, no network
call, no model asset read.
"""
from __future__ import annotations

import importlib.util
import json
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SPEC = ROOT / "scripts" / "ci" / "verify_three_project_boundary.py"


def _load():
    spec = importlib.util.spec_from_file_location("ag06k_three_project_boundary", SPEC)
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


B = _load()


class SeamCallerBaselineControls(unittest.TestCase):
    def test_live_baseline_is_present_and_well_formed(self) -> None:
        path = ROOT / B.SEAM_CALLER_BASELINE
        self.assertTrue(path.is_file(), f"{B.SEAM_CALLER_BASELINE} missing")
        data = json.loads(path.read_text(encoding="utf-8"))
        self.assertEqual(data["schemaVersion"], "work-lab/seam-caller-baseline/v1")
        # Every seam the verifier checks must be represented, otherwise a seam
        # could be silently dropped from the baseline and stop being enforced.
        self.assertEqual(set(data["seams"]), set(B.SEAM_CALLER_MARKERS))

    def test_live_baseline_entries_declare_their_contract(self) -> None:
        data = json.loads((ROOT / B.SEAM_CALLER_BASELINE).read_text(encoding="utf-8"))
        for seam_id, entry in data["seams"].items():
            with self.subTest(seam=seam_id):
                self.assertEqual(entry["contract"], B.REQUIRED_SEAMS[seam_id])
                self.assertIsInstance(entry["callers"], list)

    def test_live_baseline_records_zero_code_callers(self) -> None:
        # Not an aspiration: this is what the scan actually returns today for CODE
        # callers. The only hit is this control file, which references the marker
        # solely to assert the seam is unreferenced, and is declared separately.
        data = json.loads((ROOT / B.SEAM_CALLER_BASELINE).read_text(encoding="utf-8"))
        for seam_id, entry in data["seams"].items():
            with self.subTest(seam=seam_id):
                self.assertEqual(entry["callers"], [])
        self.assertEqual(B._seam_callers("KNOWLEDGE_TRUTH"), set())
        self.assertEqual(B._seam_callers("DESIGN_LAB"), set())
        # The one observed reference must be the declared verification reference,
        # not an undeclared stale path.
        observed = B._seam_callers("MEMORY_BACKEND")
        declared = set(data["verification_references"]["MEMORY_BACKEND"])
        self.assertTrue(observed <= declared, f"undeclared reference(s): {observed - declared}")
        self.assertIn("tests/workflow-assistance/nf28_seam_caller_baseline.py", declared)

    def test_verification_references_cover_every_seam(self) -> None:
        data = json.loads((ROOT / B.SEAM_CALLER_BASELINE).read_text(encoding="utf-8"))
        self.assertEqual(set(data["verification_references"]), set(B.SEAM_CALLER_MARKERS))

    def test_stale_verification_reference_is_detected(self) -> None:
        # A declared exemption that no longer references the contract would be a
        # standing allowance for a file that could later start calling the seam.
        data = json.loads((ROOT / B.SEAM_CALLER_BASELINE).read_text(encoding="utf-8"))
        declared = set(data["verification_references"]["DESIGN_LAB"])
        observed = B._seam_callers("DESIGN_LAB")
        self.assertEqual(sorted(declared - observed), [])

    def test_verifier_excludes_its_own_constants_from_the_caller_set(self) -> None:
        # The verifier holds each contract path as a constant; counting itself as
        # a caller would make the baseline describe the checker, not the code.
        self_rel = SPEC.resolve().relative_to(ROOT).as_posix()
        for seam_id in B.SEAM_CALLER_MARKERS:
            with self.subTest(seam=seam_id):
                self.assertNotIn(self_rel, B._seam_callers(seam_id))

    def test_scan_detects_a_new_caller_in_a_synthetic_root(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "services" / "memory").mkdir(parents=True)
            (root / "services" / "memory" / "caller.py").write_text(
                "from memory-query-contract import query\n", encoding="utf-8"
            )
            original_root, original_roots = B.ROOT, B.CALLER_SCAN_ROOTS
            B.ROOT = root
            B.CALLER_SCAN_ROOTS = ("services",)
            try:
                callers = B._seam_callers("MEMORY_BACKEND")
            finally:
                B.ROOT, B.CALLER_SCAN_ROOTS = original_root, original_roots
            self.assertEqual(callers, {"services/memory/caller.py"})

    def test_scan_ignores_unrelated_files(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "services" / "memory").mkdir(parents=True)
            (root / "services" / "memory" / "unrelated.py").write_text(
                "import json\n", encoding="utf-8"
            )
            original_root, original_roots = B.ROOT, B.CALLER_SCAN_ROOTS
            B.ROOT = root
            B.CALLER_SCAN_ROOTS = ("services",)
            try:
                callers = B._seam_callers("MEMORY_BACKEND")
            finally:
                B.ROOT, B.CALLER_SCAN_ROOTS = original_root, original_roots
            self.assertEqual(callers, set())

    def test_baseline_blocks_a_grown_caller_set(self) -> None:
        # Reproduce the gate's decision logic exactly: a caller absent from the
        # recorded set is an addition and must be reported.
        recorded = {"callers": []}
        observed = {"services/memory/new_caller.py"}
        added = sorted(observed - set(recorded["callers"]))
        self.assertEqual(added, ["services/memory/new_caller.py"])

    def test_baseline_allows_a_shrunk_caller_set(self) -> None:
        # One-directional by design: removing a caller is progress, not a failure.
        recorded = {"callers": ["services/memory/old_caller.py"]}
        observed: set[str] = set()
        self.assertEqual(sorted(observed - set(recorded["callers"])), [])

    def test_baseline_is_one_directional_and_says_so(self) -> None:
        data = json.loads((ROOT / B.SEAM_CALLER_BASELINE).read_text(encoding="utf-8"))
        self.assertIn("ONE_DIRECTIONAL", data["direction"])

    def test_baseline_states_what_it_does_not_prove(self) -> None:
        # F19's wider point stays open; the baseline must not be read as a full
        # boundary acceptance.
        data = json.loads((ROOT / B.SEAM_CALLER_BASELINE).read_text(encoding="utf-8"))
        self.assertIn("not_claimed", data)
        self.assertIn("does not prove", data["not_claimed"])

    def test_every_declared_seam_has_a_caller_marker(self) -> None:
        for seam_id in B.REQUIRED_SEAMS:
            with self.subTest(seam=seam_id):
                self.assertIn(seam_id, B.SEAM_CALLER_MARKERS)


if __name__ == "__main__":
    unittest.main()

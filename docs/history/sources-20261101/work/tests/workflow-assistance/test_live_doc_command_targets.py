"""Gate: no live instruction surface may tell a reader to run a path that does not exist.

U02 is path convergence. ERR-115 recorded that `scripts/workflow/` had moved out of the repository,
round D repaired the scripts and skills that called it — and the *documents* were never re-asked, so
77 command lines across `docs/current/`, the managed skill references, README and AGENTS.md still
instructed a path that no longer exists. This gate makes that question machine-checkable instead of
dependent on someone remembering to ask it.

Surfaces are the ones a reader acts on today. Frozen narrative (docs/history, taskpacks/history,
reports/audit-archive, knowledge-staging) is out of scope on purpose, and JSON ledgers are scanned by
their own promise-resolving gate rather than line-by-line, because a `command` field is history while
`lifecycle.regressionCommand` is a promise (ERR-130).
"""
from __future__ import annotations

import importlib.util
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SCRIPT = ROOT / "scripts" / "audit" / "live_doc_command_targets.py"

spec = importlib.util.spec_from_file_location("ldct", SCRIPT)
ldct = importlib.util.module_from_spec(spec)
spec.loader.exec_module(ldct)


class LiveDocCommandTargetsGate(unittest.TestCase):
    def setUp(self) -> None:
        self.files = ldct.tracked_files()
        self.hits = ldct.scan(self.files)
        self.unresolved = ldct.unresolved(self.hits)

    def test_the_scan_actually_reads_the_live_surfaces(self) -> None:
        self.assertGreaterEqual(len(self.files), 1500)
        self.assertTrue(any(f.startswith("docs/current/") for f in
                            [h["file"] for h in self.hits]),
                        "no hit landed in docs/current — the scope is probably wrong")
        # A not-blind floor, deliberately below the debt count (19 dead references measured 2026-10-08).
        # The floor was previously pinned to that count, so re-pointing one honest reference made the
        # guard go red for having done its job: a debt number is not a capability number.
        self.assertGreaterEqual(len(self.hits), 10,
                                "a scan that finds nothing is a scan that looks at nothing")

    def test_no_live_document_instructs_an_unexplained_dead_path(self) -> None:
        self.assertEqual(
            [{"file": h["file"], "line": h["line"], "reference": h["reference"]}
             for h in self.unresolved],
            [], "live instructions pointing at paths that do not exist, with no reason recorded")

    def test_every_repoint_target_exists_and_every_allowed_path_is_still_dead(self) -> None:
        for dead, live in ldct.MAP.items():
            self.assertTrue((ROOT / live).is_file(), f"MAP target absent: {dead} -> {live}")
            self.assertFalse((ROOT / dead).exists(), f"MAP source {dead} now exists; drop the entry")
        for path in ldct.ALLOW:
            self.assertFalse((ROOT / path).exists(), f"allowed path {path} is not dead anymore")

    def test_the_two_tables_do_not_disagree_about_a_path(self) -> None:
        self.assertEqual(sorted(set(ldct.MAP) & set(ldct.ALLOW)), [],
                         "a path cannot be both re-pointed and kept")

    def test_a_dead_path_with_a_single_tracked_namesake_is_not_silently_allowed(self) -> None:
        # catching the shape that shipped: a doc teaching `scripts/workflow/switch_model.py`
        hit = {"file": "docs/current/x.md", "line": 1,
               "reference": "scripts/workflow/switch_model.py"}
        self.assertIn(hit["reference"], ldct.MAP)
        self.assertNotIn(hit["reference"], ldct.ALLOW)

    # ---------------- negative controls on the classifier itself
    def test_an_unexplained_dead_reference_is_unresolved(self) -> None:
        hits = [{"file": "docs/current/x.md", "line": 9, "reference": "scripts/never_existed.py"}]
        self.assertEqual(len(ldct.unresolved(hits)), 1)

    def test_an_allowed_reference_is_not_reported_as_unresolved(self) -> None:
        hits = [{"file": "docs/current/x.md", "line": 9,
                 "reference": next(iter(ldct.ALLOW))}]
        self.assertEqual(ldct.unresolved(hits), [])

    def test_a_repointed_reference_is_not_reported_as_unresolved(self) -> None:
        hits = [{"file": "docs/current/x.md", "line": 9, "reference": next(iter(ldct.MAP))}]
        self.assertEqual(ldct.unresolved(hits), [])

    def test_the_extension_alternation_cannot_swallow_a_longer_one(self) -> None:
        # ERR-130's defect: `…|js|…|json` matches the `js` inside module-profile.json
        m = ldct.CMD_SHAPE.search("read apps/observer/module-profile.json now")
        self.assertIsNone(m, "the matcher matched inside a .json filename")
        m2 = ldct.CMD_SHAPE.search("node apps/observer/scripts/build.js")
        self.assertIsNotNone(m2)


if __name__ == "__main__":
    unittest.main(verbosity=2)

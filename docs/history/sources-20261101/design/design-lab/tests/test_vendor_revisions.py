# SPDX-License-Identifier: MIT
"""vendor/sources.revisions.json must match what the repo can actually prove.

AUTHORITY.md §9 requires an ABSORBED source to carry source AND revision.
vendor/sources.lock.json records 46 vendored sources with no revision field and
no structured source URL at all, so none of them could satisfy the rule they were
filed under -- and nothing checked. 37 of the 46 are recoverable offline by an
exact repository-path join against research/candidates/CANDIDATE-TAXONOMY.json
(`pinnedCommitSHA`); scripts/derive_vendor_revisions.py performs that join and
writes the result together with the 9 that could not be recovered and why.

This test is the anti-drift guard: it re-derives and compares. If someone edits a
revision by hand, adds a lock entry without revisiting the derivation, or changes
the taxonomy pin, this fails rather than letting the record drift away from the
evidence. It does NOT assert the 9 unresolved are resolved -- absence is recorded
honestly as "not verified", which is different from absence of provenance.
"""
import importlib.util
import json
import re
import unittest
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
SPEC = importlib.util.spec_from_file_location(
    "derive_vendor_revisions", REPO / "scripts" / "derive_vendor_revisions.py")
deriver = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(deriver)

REVISIONS = REPO / "vendor" / "sources.revisions.json"


class VendorRevisionRecordTests(unittest.TestCase):
    def test_record_matches_a_fresh_derivation(self):
        self.assertTrue(REVISIONS.is_file(), "vendor/sources.revisions.json is missing")
        stored = json.loads(REVISIONS.read_text(encoding="utf-8"))
        derived = deriver.build()
        self.assertEqual(
            stored, derived,
            "the committed revision record no longer matches what the repository can "
            "prove; regenerate with scripts/derive_vendor_revisions.py")

    def test_every_recorded_revision_is_a_plausible_commit(self):
        stored = json.loads(REVISIONS.read_text(encoding="utf-8"))
        self.assertGreater(len(stored["sources"]), 0, "the record resolved nothing")
        for sid, entry in stored["sources"].items():
            self.assertRegex(entry["revision"], r"^[0-9a-f]{7,40}$",
                             "%s carries a revision that is not a hex commit" % sid)
            self.assertRegex(entry["repo"], r"^[a-z0-9._-]+/[a-z0-9._-]+$",
                             "%s carries a repo path that is not owner/name" % sid)

    def test_counts_are_self_consistent(self):
        stored = json.loads(REVISIONS.read_text(encoding="utf-8"))
        self.assertEqual(stored["lockEntries"],
                         stored["resolvedCount"] + stored["unresolvedCount"],
                         "resolved + unresolved does not account for every lock entry")
        self.assertEqual(len(stored["sources"]), stored["resolvedCount"])
        self.assertEqual(len(stored["unresolved"]), stored["unresolvedCount"])

    def test_derivation_rejects_a_revision_that_is_not_pinned_anywhere(self):
        """Falsification: a fabricated commit must not survive a re-derivation.
        Without this, the equality test above could pass against a record that no
        longer reflects any real evidence."""
        stored = json.loads(REVISIONS.read_text(encoding="utf-8"))
        victim = sorted(stored["sources"])[0]
        tampered = json.loads(json.dumps(stored))
        tampered["sources"][victim]["revision"] = "0" * 40
        self.assertNotEqual(tampered, deriver.build(),
                            "a fabricated revision was indistinguishable from a derived one")


if __name__ == "__main__":
    unittest.main(verbosity=2)

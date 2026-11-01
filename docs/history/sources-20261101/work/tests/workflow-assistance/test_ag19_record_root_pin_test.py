"""AG-19 gate: the Record-root pin test may report what it measured and nothing more.

The instrument answers one of the goal's named gaps — where the missing originals actually are — over
a root no earlier proof covered (the owner's 15 GB material root, 114 files and 31,382 archive
members). What matters for trust is not the size of that sweep but that its verdict cannot inflate:

* a hash claim requires a hash match, and an unpinned atlas item (no `expected_sha256`) can never be
  disproved by hash at all, so the record must say so;
* a filename match is only a lead, and a hit belonging to another project must not be counted as
  ours;
* a machine without the root must return SCOPE_NOT_AVAILABLE_ON_THIS_MACHINE rather than quietly
  reporting an absence it did not observe.

Discovered dynamically by `run_quality_gate.py governance`.
"""
from __future__ import annotations

import hashlib
import importlib.util
import json
import subprocess
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SCRIPT = ROOT / "scripts" / "audit" / "ag19_record_root_pin_test.py"
RECORD = ROOT / "docs" / "audits" / "AG19_RECORD_ROOT_PIN_TEST_2026-10-07.json"
SCRATCH = ROOT / ".project-local" / "runs" / "ag19-record-root-pin-test-gate"

spec = importlib.util.spec_from_file_location("ag19rr", SCRIPT)
ag19 = importlib.util.module_from_spec(spec)
spec.loader.exec_module(ag19)

NEGATIVE_VERDICTS = {
    "NEGATIVELY_PROVEN_ALL_TARGETS_PINNED_IN_SCOPE",
    "NEGATIVELY_PROVEN_FOR_PINNED_TARGETS_ONLY_UNPINNED_HAVE_NO_HASH_PROOF",
    "IN_SCOPE_NEGATIVE_PROOF",
}


def run(root: str, tag: str) -> subprocess.CompletedProcess:
    SCRATCH.mkdir(parents=True, exist_ok=True)
    return subprocess.run(
        [sys.executable, str(SCRIPT), "--root", root,
         "--json-out", f".project-local/runs/ag19-record-root-pin-test-gate/{tag}_detail.json",
         "--record", str(SCRATCH / f"{tag}_record.json")],
        cwd=ROOT, capture_output=True, text=True, encoding="utf-8", errors="replace")


class PureFunctionTests(unittest.TestCase):
    def test_normalize_catches_the_export_suffix_that_hides_the_only_real_candidate(self) -> None:
        # the atlas pins `…-2026-09-03(1).md`; the archive member is `…-2026-09-03.md`. An exact-name
        # test would have missed the one hit in scope that actually matches a pinned digest.
        self.assertEqual(ag19.normalize("WORK-LAB-NEW-CHAT-HANDOFF-2026-09-03(1).md"),
                         ag19.normalize("WORK-LAB-NEW-CHAT-HANDOFF-2026-09-03.md"))
        self.assertNotEqual(ag19.normalize("WORK-LAB-SUMMARY.md"),
                            ag19.normalize("WORK-LAB-SUMMARY-2.md"))

    def test_attribution_never_gives_another_project_file_to_this_project(self) -> None:
        self.assertEqual(ag19.attribute("AAOS_ArcheAxis_最终执行任务文档_2026-09-28.docx"), "otherProject")
        self.assertEqual(ag19.attribute("DESIGN-LAB_MASTER_ATLAS_recovery.md"), "otherProject")
        self.assertEqual(ag19.attribute("三项目_AI生态全生命周期收敛实施清单.json"), "otherProject")
        self.assertEqual(ag19.attribute("WORK-LAB-NEW-CHAT-HANDOFF-2026-09-03.md"), "worklab")
        # a name carrying both identities belongs to the other project: checked first, on purpose
        self.assertEqual(ag19.attribute("AAOS_WORK-LAB-notes.md"), "otherProject")
        self.assertEqual(ag19.attribute("00_总控启动提示词.md"), "unattributed")

    def test_a_verdict_cannot_claim_a_negative_proof_over_a_hash_match(self) -> None:
        targets = [{"pinId": "A", "name": "a.md", "pinned": True, "expectedBytes": 10,
                    "expectedSha256": "x"}, {"pinId": "B", "name": "b.md", "pinned": False,
                                              "expectedBytes": None, "expectedSha256": None}]
        empty = {"files": 5, "zipMembers": 5, "sizeHits": [], "digestHits": [], "nameHits": [],
                 "unreadable": []}
        hit = dict(empty, digestHits=[{"pinId": "A", "kind": "file", "relative": "a.md"}])
        self.assertEqual(ag19.verdict_for(targets, True, hit), "PIN_MATCH_FOUND_EXTRACTION_OWED")
        self.assertEqual(ag19.verdict_for(targets, True, empty),
                         "NEGATIVELY_PROVEN_FOR_PINNED_TARGETS_ONLY_UNPINNED_HAVE_NO_HASH_PROOF")
        all_pinned = [dict(targets[0])]
        self.assertEqual(ag19.verdict_for(all_pinned, True, empty),
                         "NEGATIVELY_PROVEN_ALL_TARGETS_PINNED_IN_SCOPE")

    def test_a_missing_root_never_produces_an_absence_claim(self) -> None:
        self.assertEqual(ag19.verdict_for([{"pinId": "A", "pinned": True}], False,
                                          {"files": 0, "zipMembers": 0, "sizeHits": [],
                                           "digestHits": [], "nameHits": [], "unreadable": []}),
                         "SCOPE_NOT_AVAILABLE_ON_THIS_MACHINE")


class ShippedRecordTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        assert RECORD.is_file(), f"missing {RECORD}"
        cls.doc = json.loads(RECORD.read_text(encoding="utf-8"))

    def test_counts_are_derived_from_the_record_own_lists(self) -> None:
        c = self.doc["counts"]
        self.assertEqual(c["contentHits"], len(self.doc["contentHits"]))
        self.assertEqual(c["digestHits"], len(self.doc["digestHits"]))
        self.assertEqual(c["nameHits"], len(self.doc["nameHits"]))
        self.assertEqual(sum(c["nameHitsByAttribution"].values()), c["nameHits"])
        self.assertEqual(sum(c["contentHitsByBasis"].values()), c["contentHits"])
        self.assertEqual(c["pinnedTargets"] + c["unpinnedTargets"], len(self.doc["targets"]))

    def test_unpinned_targets_make_no_hash_or_size_claim(self) -> None:
        for t in self.doc["targets"]:
            if not t["pinned"]:
                self.assertIsNone(t["expectedSha256"], f"{t['pinId']} claims a digest while unpinned")
                self.assertFalse(t["expectedBytes"], f"{t['pinId']} claims a size while unpinned")
        if self.doc["counts"]["unpinnedTargets"]:
            joined = " ".join(self.doc["whatThisDoesNotProve"])
            self.assertRegex(joined, r"(?i)unpinned",
                             "the record leaves unpinned targets without stating the hash limit")

    def test_no_digest_hit_exists_that_does_not_match_its_pin(self) -> None:
        by_pin = {t["pinId"]: t for t in self.doc["targets"]}
        for hit in self.doc["digestHits"]:
            self.assertIn(hit["pinId"], by_pin)
            lead = next(h for h in self.doc["contentHits"]
                        if h.get("member") == hit.get("member") or h.get("relative") == hit.get("relative"))
            self.assertEqual(lead["sha256"], by_pin[hit["pinId"]]["expectedSha256"],
                             "a reported recovery does not equal the pinned digest")
            self.assertEqual(lead["matchBasis"], hit["basis"])

    def test_the_scope_is_stated_in_numbers_not_adjectives(self) -> None:
        scope = self.doc["scope"]
        self.assertTrue(scope["rootPresent"])
        self.assertGreaterEqual(scope["filesEnumerated"], 100)
        self.assertGreaterEqual(scope["zipMembersEnumerated"], 30000,
                                "a sweep that did not read the archives cannot call itself a "
                                "negative proof over the root")
        self.assertIn("central directory", scope["method"])
        self.assertEqual(self.doc["counts"]["unreadable"], 0)

    def test_worklab_name_hits_must_have_been_content_checked(self) -> None:
        worklab = [h for h in self.doc["nameHits"] if h["attribution"] == "worklab"]
        checked = {h.get("member") or h.get("relative") for h in self.doc["contentHits"]}
        for hit in worklab:
            key = hit.get("member") or hit.get("relative")
            self.assertIn(key, checked,
                          f"a WORK-LAB-attributed name hit ({key}) was never content-checked")

    def test_machine_local_extraction_bytes_are_not_opened(self) -> None:
        """Do not open a machine-local recovery source just to recheck its digest."""
        self.skipTest(
            "machine-local recovery bytes are user material and stay unread; "
            "the tracked report's digest and recovery status are checked structurally"
        )


class RuntimeBehaviourTests(unittest.TestCase):
    def test_a_run_without_the_root_refuses_to_claim_an_absence(self) -> None:
        proc = run(str(ROOT / ".project-local" / "definitely-not-here"), "noroot")
        self.assertEqual(proc.returncode, 0, proc.stdout + proc.stderr)
        doc = json.loads((SCRATCH / "noroot_record.json").read_text(encoding="utf-8"))
        self.assertEqual(doc["verdict"], "SCOPE_NOT_AVAILABLE_ON_THIS_MACHINE")
        self.assertIs(doc["scope"]["rootPresent"], False)
        self.assertEqual(doc["counts"]["digestHits"], 0)
        joined = " ".join(doc["whatThisDoesNotProve"])
        self.assertIn("SCOPE_NOT_AVAILABLE_ON_THIS_MACHINE", joined,
                      "the record does not tell a reader that its absence claims are unavailable here")

    def test_a_synthetic_root_reproduces_the_hit_and_the_negative_paths(self) -> None:
        fake = SCRATCH / "fake-root"
        fake.mkdir(parents=True, exist_ok=True)
        for stale in fake.glob("*"):
            if stale.is_file():
                stale.unlink()
        # a file at a pinned size with DIFFERENT bytes must be reported as a lead, not a recovery.
        # The summary pin (164,397 B) is used rather than the timeline's 15.5 MB so the fixture stays
        # small; the semantics being tested are identical.
        summary = next(t for t in ag19.load_targets()[0] if t["pinId"] == "SRC-WL-SUMMARY")
        (fake / "same-size-different-bytes.md").write_bytes(b"x" * int(summary["expectedBytes"]))
        proc = run(str(fake), "synthetic")
        self.assertEqual(proc.returncode, 0, proc.stdout + proc.stderr)
        doc = json.loads((SCRATCH / "synthetic_record.json").read_text(encoding="utf-8"))
        self.assertEqual(doc["counts"]["digestHits"], 0)
        self.assertEqual(doc["counts"]["contentHits"], 1)
        self.assertEqual(doc["contentHits"][0]["pinMatches"], None)
        self.assertEqual(doc["verdict"],
                         "NEGATIVELY_PROVEN_FOR_PINNED_TARGETS_ONLY_UNPINNED_HAVE_NO_HASH_PROOF")

    def test_the_preferred_pin_source_is_a_file_a_clean_checkout_also_has(self) -> None:
        """The promotion only matters if the scan actually reads the versioned copy.

        Before it, a runner silently fell back to the last published list, so the pins this gate
        checks could differ from the atlas without anything noticing.
        """
        targets, source = ag19.load_targets()
        self.assertEqual(source, "tracked-promoted-copy",
                         "the scan is not reading the promoted copy, so CI cannot see the pins")
        self.assertGreaterEqual(len(targets), 5, "the versioned pin list is shorter than the five AG-19 items")
        self.assertEqual(subprocess.run(["git", "ls-files", "--error-unmatch",
                                         str(ag19.TRACKED_ATLAS.relative_to(ag19.REPO))],
                                        cwd=ag19.REPO, capture_output=True).returncode, 0,
                         "the preferred pin source is not versioned")
        if ag19.ATLAS.is_file():
            self.assertEqual(ag19.TRACKED_ATLAS.read_bytes(), ag19.ATLAS.read_bytes(),
                             "the promoted copy and the atlas the machine still holds have diverged")


if __name__ == "__main__":
    unittest.main()

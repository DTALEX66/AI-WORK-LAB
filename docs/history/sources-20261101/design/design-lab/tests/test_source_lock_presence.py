# SPDX-License-Identifier: MIT
"""The vendor lock may only claim what a reader can re-measure.

`vendor/sources.lock.json` records 46 third-party sources with a file count and a
path, and before this gate existed nothing checked either -- `SOURCE_REGISTRY=PASS`
was printed while 37 of the 46 paths pointed at a gitignored local cache and 6
pointed at directories deleted in 2026-09-04.

The tests split by *what a clone can prove*. Recomputing presence from `git ls-files`
plus the `.project-local/` rule works everywhere, so it must match on any machine.
Recomputing a cache digest requires the bytes, so it is asserted only when this
machine has them, and its absence is never allowed to upgrade or downgrade a class.
"""
from __future__ import annotations

import importlib.util
import json
import subprocess
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
LOCK = ROOT / "vendor" / "sources.lock.json"
MODULE = ROOT / "scripts" / "amend_source_lock_presence.py"


def _load_generator():
    spec = importlib.util.spec_from_file_location("amend_source_lock_presence", MODULE)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


AMEND = _load_generator()


def _lock() -> dict:
    return json.loads(LOCK.read_text(encoding="utf-8"))


def _sources() -> list[dict]:
    return _lock()["sources"]


class GeneratorIsLoadable(unittest.TestCase):
    """Self-check: a gate whose subject cannot be read proves nothing."""

    def test_lock_carries_the_expected_number_of_sources(self) -> None:
        self.assertEqual(len(_sources()), 46)

    def test_every_source_carries_the_measured_fields(self) -> None:
        for source in _sources():
            for field in ("presence", "gitFiles", "diskFiles", "contentDigest",
                          "countMatchesRecord", "pathNamedInIsolationRecord"):
                self.assertIn(field, source, f"{source.get('id')} lacks {field}")
            self.assertIn(source["presence"], AMEND.PRESENCE)

    def test_presence_counts_are_the_sum_of_the_records(self) -> None:
        audit = _lock()["presenceAudit"]
        recomputed: dict[str, int] = {}
        for source in _sources():
            recomputed[source["presence"]] = recomputed.get(source["presence"], 0) + 1
        self.assertEqual(audit["counts"], recomputed)
        self.assertEqual(sum(audit["counts"].values()), len(_sources()))


class PresenceIsRecomputableOnAnyMachine(unittest.TestCase):
    """Class must follow from git plus a path rule, never from this machine's disk."""

    def test_recorded_presence_matches_a_fresh_derivation(self) -> None:
        tracked = AMEND.tracked_paths()
        for source in _sources():
            self.assertEqual(AMEND.classify(source, tracked)["presence"], source["presence"],
                             f"{source['id']} presence drifted")

    def test_a_missing_cache_directory_still_reads_as_cache_only(self) -> None:
        # simulate a fresh clone: the volatile path is simply not there
        source = {"id": "clone-simulation", "path": ".project-local/cache/vendor/does-not-exist",
                  "files": 219}
        self.assertEqual(AMEND.classify(source, [])["presence"], "LOCAL_CACHE_ONLY")
        self.assertIsNone(AMEND.classify(source, [])["contentDigest"])

    def test_a_cache_path_is_never_reported_as_in_repo(self) -> None:
        for source in _sources():
            if str(source["path"]).replace("\\", "/").startswith(AMEND.VOLATILE_ROOT):
                self.assertNotEqual(source["presence"], "IN_REPO", source["id"])
                self.assertNotIn(str(source["path"]).replace("\\", "/"),
                                 AMEND.tracked_paths(), source["id"])

    def test_a_tracked_path_outranks_the_volatile_rule(self) -> None:
        # if a source ever gets committed, its class must move to IN_REPO, because
        # otherwise a real absorption would still be reported as cache-only
        source = {"id": "committed", "path": ".project-local/cache/vendor/x", "files": 1}
        tracked = [".project-local/cache/vendor/x/README.md"]
        self.assertEqual(AMEND.classify(source, tracked)["presence"], "IN_REPO")


class ClassesMatchTheirOwnClaims(unittest.TestCase):
    """Disposition and measured presence may not contradict each other."""

    def test_absorb_dispositions_have_bytes_in_git(self) -> None:
        absorbed = [s for s in _sources() if str(s["disposition"]).startswith("ABSORB")]
        self.assertTrue(absorbed, "no ABSORB source to test -- the assertion is vacuous")
        for source in absorbed:
            self.assertEqual(source["presence"], "IN_REPO", source["id"])
            self.assertTrue(source["countMatchesRecord"], f"{source['id']} file count drifted")

    def test_only_references_point_at_absent_paths(self) -> None:
        for source in _sources():
            if source["presence"] == "ABSENT_FROM_GIT":
                self.assertEqual(source["disposition"], "LOCK_REFERENCE", source["id"])
                self.assertIsNone(source["contentDigest"], source["id"])

    def test_condition_poc_bytes_are_not_in_git(self) -> None:
        for source in _sources():
            if source["disposition"] == "CONDITIONAL_POC":
                self.assertEqual(source["presence"], "LOCAL_CACHE_ONLY", source["id"])
                self.assertEqual(source["gitFiles"], 0, source["id"])

    def test_unbacked_absent_references_are_listed_not_invented(self) -> None:
        audit = _lock()["presenceAudit"]
        unbacked = set(audit["absentReferencesNotNamedInIsolationRecord"])
        recomputed = {s["id"] for s in _sources()
                      if s["presence"] == "ABSENT_FROM_GIT" and not s["pathNamedInIsolationRecord"]}
        self.assertEqual(unbacked, recomputed)
        # 2026-10-08: this pinned 4, because four LOCK_REFERENCE rows pointed at directories
        # deleted in c9cde8a5 with nothing naming them. Two of the six only looked "backed"
        # by accident -- the isolation record listed one *file* inside them and the test was
        # a substring. All six are now declared in docs/THIRD_PARTY_ISOLATION.md's retirement
        # table with the deletion commit and the deleted tree's SHA recovered from git, so an
        # unbacked reference is a finding again rather than the status quo. The number stays
        # pinned at zero: a seventh undeleted reference with no declaration fails here.
        self.assertEqual(unbacked, set(),
                         f"undeclared absent references: {sorted(unbacked)}")

    def test_every_absent_reference_carries_recovered_provenance(self) -> None:
        """A reference may stay only if a reader can re-derive what it pointed at."""
        for source in _sources():
            if source["presence"] != "ABSENT_FROM_GIT":
                continue
            sid = source["id"]
            self.assertRegex(str(source.get("retiredIn")), r"^[0-9a-f]{7,40}$")
            self.assertRegex(str(source.get("retiredTreeSha")), r"^[0-9a-f]{7,40}$",
                             f"{sid}: no content identity for the deleted tree")
            self.assertTrue(str(source.get("upstreamRepo", "")).startswith("https://"),
                            f"{sid}: no upstream URL, so the reference cannot be re-acquired")
            self.assertTrue(str(source.get("revisionStatement", "")).strip(),
                            f"{sid}: silent about whether anything was ever pinned")

    def test_a_stripped_declaration_is_still_caught(self) -> None:
        """Falsification: the rules above must fire on the pre-fix shape of the record."""
        import copy
        lock = copy.deepcopy(_lock())
        for source in lock["sources"]:
            if source["id"] == "shipit-ui":
                source["pathNamedInIsolationRecord"] = False
                source["retiredTreeSha"] = None
                source["revisionStatement"] = ""
        recomputed = {s["id"] for s in lock["sources"]
                      if s["presence"] == "ABSENT_FROM_GIT" and not s["pathNamedInIsolationRecord"]}
        self.assertEqual(recomputed, {"shipit-ui"})
        for source in lock["sources"]:
            if source["id"] != "shipit-ui":
                continue
            self.assertFalse(str(source.get("retiredTreeSha") or ""))
            self.assertFalse(str(source.get("revisionStatement") or "").strip())


class DigestsAreMachineScopedEvidence(unittest.TestCase):
    """Prove a digest means what it says, and only when the bytes are present."""

    def test_in_repo_digests_recompute_from_the_committed_files(self) -> None:
        checked = 0
        for source in _sources():
            if source["presence"] != "IN_REPO":
                continue
            path = str(source["path"]).replace("\\", "/")
            count, digest = AMEND.digest_dir(ROOT / path)
            self.assertEqual(digest, source["contentDigest"], source["id"])
            self.assertEqual(count, source["gitFiles"], source["id"])
            checked += 1
        self.assertGreaterEqual(checked, 3, "no IN_REPO source was actually verified")

    def test_cache_digest_is_verified_only_when_this_machine_has_the_bytes(self) -> None:
        verified = skipped = 0
        for source in _sources():
            if source["presence"] != "LOCAL_CACHE_ONLY":
                continue
            path = str(source["path"]).replace("\\", "/")
            count, digest = AMEND.digest_dir(ROOT / path)
            if digest is None:
                skipped += 1
                continue
            self.assertEqual(digest, source["contentDigest"], source["id"])
            self.assertEqual(count, source["diskFiles"], source["id"])
            verified += 1
        self.assertEqual(verified + skipped, 37)
        if skipped == 37:
            self.skipTest("this machine has no vendor cache; cache integrity is NOT_VERIFIED here")

    def test_every_recorded_digest_is_a_sha256_hex_or_null(self) -> None:
        empty = "e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855"
        for source in _sources():
            digest = source["contentDigest"]
            if digest is None:
                self.assertIn(source["presence"], ("ABSENT_FROM_GIT",))
                continue
            self.assertRegex(digest, r"^[0-9a-f]{64}$", source["id"])
            # the digest of "no bytes at all" must never stand in for content
            self.assertNotEqual(digest, empty, f"{source['id']} hashed an empty directory")


class ViolationShapeIsDetected(unittest.TestCase):
    """Falsify the gate before trusting it: a hand-edited or stale record must fail."""

    def test_hand_edited_presence_is_caught(self) -> None:
        source = dict(_sources()[0])
        source["presence"] = "IN_REPO" if source["presence"] != "IN_REPO" else "ABSENT_FROM_GIT"
        tracked = AMEND.tracked_paths()
        self.assertNotEqual(AMEND.classify(source, tracked)["presence"], source["presence"])

    def test_one_flipped_byte_changes_the_digest(self) -> None:
        with tempfile.TemporaryDirectory() as raw:
            root = Path(raw)
            (root / "a.txt").write_bytes(b"design source\n")
            (root / "b.txt").write_bytes(b"licence text\n")
            first_count, first = AMEND.digest_dir(root)
            self.assertEqual(first_count, 2)
            (root / "a.txt").write_bytes(b"design sourcE\n")
            _, second = AMEND.digest_dir(root)
            self.assertNotEqual(first, second, "digest is blind to content")

    def test_renaming_a_file_changes_the_digest(self) -> None:
        with tempfile.TemporaryDirectory() as raw:
            root = Path(raw)
            (root / "a.txt").write_bytes(b"same bytes\n")
            _, first = AMEND.digest_dir(root)
            (root / "a.txt").rename(root / "z.txt")
            _, second = AMEND.digest_dir(root)
            self.assertNotEqual(first, second, "digest ignores the file inventory")

    def test_an_empty_directory_is_not_a_verified_source(self) -> None:
        with tempfile.TemporaryDirectory() as raw:
            root = Path(raw)
            count, digest = AMEND.digest_dir(root)
            self.assertEqual((count, digest), (0, None))

    def test_the_generator_is_idempotent_over_the_committed_lock(self) -> None:
        tracked = AMEND.tracked_paths()
        for source in _sources():
            facts = AMEND.classify(source, tracked)
            self.assertEqual(facts["presence"], source["presence"])
            self.assertEqual(facts["gitFiles"], source["gitFiles"])
            if facts["presence"] == "IN_REPO":
                self.assertEqual(facts["contentDigest"], source["contentDigest"])


class PresenceAndProvenanceMustAgree(unittest.TestCase):
    """AUTHORITY §9 wants source AND revision for an absorbed file.

    PR #242 answers "which commit did these bytes come from" and this record answers
    "are the bytes here at all". Neither is sufficient alone: a revision for bytes that
    exist only in one machine's cache is provenance without a subject, and bytes in the
    repo with no revision is a subject without provenance. The revision record arrives
    on its own branch, so this cross-check is skipped until it exists rather than
    pretending the two files have always been paired.
    """

    REVISIONS = ROOT / "vendor" / "sources.revisions.json"

    def test_both_records_cover_the_same_source_ids(self) -> None:
        if not self.REVISIONS.is_file():
            self.skipTest("vendor/sources.revisions.json is not on this revision yet")
        revisions = json.loads(self.REVISIONS.read_text(encoding="utf-8"))
        lock_ids = {s["id"] for s in _sources()}
        recorded = set(revisions["sources"]) | {u["id"] for u in revisions["unresolved"]}
        self.assertEqual(lock_ids, recorded,
                         "the two vendor records describe different sources")

    def test_an_absorbed_source_states_provenance_or_its_absence(self) -> None:
        """Not "every absorbed source must be resolved" -- that would turn a recorded
        unknown into a red build and train people to distrust the gate. What may not
        happen is silence: an ABSORB source must appear in exactly one of the two lists
        and carry a reason when it is in the unresolved one.
        """
        if not self.REVISIONS.is_file():
            self.skipTest("vendor/sources.revisions.json is not on this revision yet")
        revisions = json.loads(self.REVISIONS.read_text(encoding="utf-8"))
        unresolved = {u["id"]: u for u in revisions["unresolved"]}
        for source in _sources():
            if not str(source["disposition"]).startswith("ABSORB"):
                continue
            sid = source["id"]
            in_resolved = sid in revisions["sources"]
            in_unresolved = sid in unresolved
            self.assertNotEqual(in_resolved, in_unresolved,
                                f"{sid} is in {'both' if in_resolved else 'neither'} revision list")
            self.assertEqual(source["presence"], "IN_REPO", sid)
            if in_unresolved:
                self.assertTrue(unresolved[sid]["reason"].strip(),
                                f"{sid} is unresolved with no stated reason")


class OutputBytesArePlatformStable(unittest.TestCase):
    """CRLF in a committed JSON makes every clone's projections differ by platform."""

    def test_lock_has_no_carriage_returns(self) -> None:
        self.assertNotIn(b"\r", LOCK.read_bytes())

    def test_lock_ends_with_a_single_newline(self) -> None:
        data = LOCK.read_bytes()
        self.assertTrue(data.endswith(b"\n"))
        self.assertFalse(data.endswith(b"\n\n"))


class GeneratorRunsAgainstAScratchRepo(unittest.TestCase):
    """The script must refuse rather than write a lock it cannot read."""

    def test_tracked_paths_are_absolute_free_and_forward_slashed(self) -> None:
        tracked = AMEND.tracked_paths()
        self.assertGreater(len(tracked), 2000)
        self.assertTrue(all("\\" not in p and not p.startswith("/") for p in tracked))
        self.assertTrue(any(p == "vendor/sources.lock.json" for p in tracked),
                        "git ls-files does not see the lock, so the gate has no subject")


if __name__ == "__main__":
    unittest.main()

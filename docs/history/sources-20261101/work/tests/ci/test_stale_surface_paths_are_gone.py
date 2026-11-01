"""The 2026-10-19 archive normalization must not be re-indexable.

`scripts/ci/verify_stale_surface_paths.py` is the only guard that looks at the WHOLE active
surface -- the authority-index gate sees `docs/current/` plus three named files, so a stale
pointer in `.project/governance/`, `scripts/`, `tests/` or `apps/` would pass every other gate.
These tests keep that guard from becoming decoration: a planted old path must convict, the frozen
`original-tree/` spelling must NOT convict, and an allowance that stops being used must convict.

This module lives in `tests/ci/` on purpose: `scripts/ci/run_root_governance_suite.py` globs that
directory, so the gate is measured by CI the moment it lands instead of waiting to be registered.
"""

from __future__ import annotations

import hashlib
import importlib.util
import json
import shutil
import subprocess
import tempfile
import unittest
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
VERIFIER = ROOT / "scripts" / "ci" / "verify_stale_surface_paths.py"
MANIFEST = ROOT / "docs/history/archive/MOVED-PATHS-20261019.json"


def _load():
    spec = importlib.util.spec_from_file_location("verify_stale_surface_paths", VERIFIER)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


MODULE = _load()


def _runtime_root() -> Path:
    """Scratch stays inside the declared project boundary (ERR-140 convention)."""
    path = ROOT / ".project-local/runs"
    path.mkdir(parents=True, exist_ok=True)
    return path


LFS_POINTER = b"version https://git-lfs.github.com/spec/v1"


def open_archive(path: Path) -> zipfile.ZipFile:
    """Name a missing LFS object instead of letting `zipfile` invent a verdict for it.

    Measured on the 2026-10-20 exact-SHA run: the consolidation archive is LFS-routed by policy, and a
    checkout without `lfs: true` leaves a 135-byte pointer where the ZIP should be. What CI reported was
    two tracebacks and a hash mismatch - three findings, none of which said the one thing that was wrong.
    A red you cannot act on gets re-run; a red that names its precondition gets fixed.
    """
    if not path.is_file():
        raise AssertionError(f"ARCHIVE_MISSING {path.relative_to(ROOT).as_posix()}")
    if path.read_bytes()[:len(LFS_POINTER)] == LFS_POINTER:
        raise AssertionError(
            f"LFS_NOT_FETCHED {path.relative_to(ROOT).as_posix()} is still an LFS pointer, so the "
            "deletion evidence cannot be read from it; the checkout must fetch large files "
            "(actions/checkout with lfs: true)")
    return zipfile.ZipFile(path)


class LiveTree(unittest.TestCase):
    def test_the_live_tree_is_clean_and_the_verdict_is_named(self) -> None:
        self.assertEqual(0, MODULE.main([]))

    def test_the_population_is_measured_not_assumed(self) -> None:
        manifest = MODULE.load_manifest(MANIFEST)
        result = MODULE.scan(ROOT, manifest)
        self.assertGreaterEqual(result["scanned"], MODULE.SCAN_FLOOR,
                                "a scan below the floor is a blind instrument, not a clean tree")
        self.assertEqual(54, manifest["counts"]["moves"])
        # every moved-from path, every deleted archive member and every forbidden prefix must be
        # in the matcher; a number that cannot be re-derived from the record proves nothing
        expected = ({move["from"] for move in manifest["moves"] if "/" in move["from"]}
                    | set(manifest["consolidation"]["deletedPaths"])
                    | {entry["prefix"] for entry in manifest["forbiddenPrefixes"]})
        self.assertEqual(len(expected), len(MODULE.old_patterns(manifest)),
                         "the gate stopped seeing part of the record it is built from")

    def test_every_moved_file_lives_at_its_new_path_with_the_recorded_bytes(self) -> None:
        """The hash chain runs root -> archive path -> ZIP member, and every link is checked."""
        manifest = MODULE.load_manifest(MANIFEST)
        archive = ROOT / manifest["consolidation"]["archive"]
        with open_archive(archive) as bundle:
            for move in manifest["moves"]:
                if "removedInto" in move:
                    with bundle.open(move["to"]) as handle:
                        raw = handle.read()
                    self.assertEqual(move["sha256"], hashlib.sha256(raw).hexdigest(),
                                     f"archive member differs from the move record: {move['to']}")
                    self.assertFalse((ROOT / move["to"]).exists(),
                                     f"consolidated file is still loose: {move['to']}")
                    continue
                target = ROOT / move["to"]
                self.assertTrue(target.is_file(), f"moved file missing: {move['to']}")
                blob = MODULE.tracked_blob(ROOT, move["to"])
                self.assertEqual(move["sha256"], hashlib.sha256(blob).hexdigest(),
                                 f"bytes differ from the move record: {move['to']}")
                self.assertEqual(move["bytes"], len(blob), f"size differs: {move['to']}")
                # A clean checkout materializes LF while this worktree may hold CRLF; the words must
                # still be identical, which is the only cross-host statement a move record can make.
                self.assertEqual(target.read_bytes().decode("utf-8").replace("\r\n", "\n"),
                                 blob.decode("utf-8"), f"worktree text differs from the blob: {move['to']}")

    def test_the_consolidated_archive_is_whole_and_its_members_are_all_gone_from_the_tree(self) -> None:
        """Deletion is only defensible because one artifact holds every byte, provably."""
        manifest = MODULE.load_manifest(MANIFEST)
        block = manifest["consolidation"]
        archive = ROOT / block["archive"]
        record = json.loads((ROOT / block["manifest"]).read_text(encoding="utf-8"))
        self.assertEqual(block["archiveSha256"], hashlib.sha256(archive.read_bytes()).hexdigest())
        self.assertEqual(block["members"], len(record["members"]))
        tracked = set(MODULE.tracked_files(ROOT))
        with open_archive(archive) as bundle:
            self.assertEqual(sorted(bundle.namelist()),
                             sorted(entry["path"] for entry in record["members"]))
            for entry in record["members"]:
                with bundle.open(entry["path"]) as handle:
                    raw = handle.read()
                self.assertEqual(entry["sha256"], hashlib.sha256(raw).hexdigest(), entry["path"])
                self.assertEqual(entry["bytes"], len(raw), entry["path"])
                self.assertEqual(zipfile.crc32(raw) & 0xFFFFFFFF, entry["crc32"], entry["path"])
                self.assertNotIn(entry["path"], tracked,
                                 f"consolidated file is still tracked: {entry['path']}")
                self.assertFalse((ROOT / entry["path"]).exists(), entry["path"])

    def test_every_archive_member_is_reproducible_from_git_history(self) -> None:
        """The deletion promise is checkable without trusting the builder that made it.

        Each member records the Git ref that still holds its bytes. Re-deriving the sha256 from that
        ref proves the archive is a copy of committed content, not of whatever was on this machine.
        """
        block = MODULE.load_manifest(MANIFEST)["consolidation"]
        record = json.loads((ROOT / block["manifest"]).read_text(encoding="utf-8"))
        with zipfile.ZipFile(ROOT / block["archive"]) as bundle:
            for entry in record["members"]:
                ref = entry.get("provenance")
                self.assertTrue(ref, f"member without provenance: {entry['path']}")
                blob = subprocess.run(["git", "cat-file", "blob", ref], cwd=ROOT,
                                      capture_output=True)
                self.assertEqual(0, blob.returncode, f"provenance ref unresolvable: {ref}")
                self.assertEqual(entry["sha256"], hashlib.sha256(blob.stdout).hexdigest(),
                                 entry["path"])
                self.assertEqual(entry["sha256"],
                                 hashlib.sha256(bundle.read(entry["path"])).hexdigest(),
                                 entry["path"])

    def test_the_formerly_governed_handoffs_are_archived_and_gone(self) -> None:
        """Four documents were kept on 2026-10-19 morning because a pointer named them.

        The owner then authorized moving the pointers, so the protected reason must be empty and each
        named path must be an archive member and absent from the tree -- checked here so a future
        reader cannot mistake the old exemption for a standing one.
        """
        block = MODULE.load_manifest(MANIFEST)["consolidation"]
        self.assertEqual({}, block["keptInPlace"])
        record = json.loads((ROOT / block["manifest"]).read_text(encoding="utf-8"))
        members = {entry["path"] for entry in record["members"]}
        formerly_governed = (
            "taskpacks/history/pre-convergence-20261019/HERMES-UPDATE-HANDOFF-20260927.md",
            "taskpacks/history/pre-convergence-20261019/WORK-LAB-UI-PROMPT-PACK-EXECUTION-TASKCARD-20261007.md",
            "taskpacks/history/pre-convergence-20261019/SESSION-HANDOFF-P0C-20261006.md",
            "taskpacks/history/WORK-LAB-EXECUTION-EFFICIENCY-REPAIR-HANDOFF.md",
        )
        for path in formerly_governed:
            self.assertIn(path, members, path)
            self.assertFalse((ROOT / path).exists(), path)
        index = json.loads((ROOT / ".project/governance/taskpack-authority-index.json")
                           .read_text(encoding="utf-8"))
        for collection in ("staticHandoffViews", "frozenTaskCards", "currentTaskCards"):
            for entry in index.get(collection, []):
                value = json.dumps(entry, ensure_ascii=False)
                for path in formerly_governed:
                    self.assertNotIn(path, value, f"{collection} still names {path}")

    def test_no_enforced_old_path_still_exists_on_disk(self) -> None:
        manifest = MODULE.load_manifest(MANIFEST)
        for move in manifest["moves"]:
            if "/" not in move["from"]:
                continue
            self.assertFalse((ROOT / move["from"]).exists(),
                             f"old path is back on disk: {move['from']}")
        for entry in manifest["forbiddenPrefixes"]:
            self.assertFalse((ROOT / entry["prefix"]).exists(),
                             f"old directory is back on disk: {entry['prefix']}")

    def test_the_recorded_basename_moves_are_not_present_at_the_root(self) -> None:
        """The seven basename moves cannot be path-matched, so the root itself is checked."""
        manifest = MODULE.load_manifest(MANIFEST)
        names = manifest["notEnforced"]["paths"]
        self.assertEqual(7, len(names), names)
        for name in names:
            self.assertFalse((ROOT / name).exists(), f"{name} reappeared at the repository root")


    def test_no_active_surface_names_a_deleted_archive_member(self) -> None:
        """Live check: the whole active population, not only the synthetic case below."""
        manifest = MODULE.load_manifest(MANIFEST)
        result = MODULE.scan(ROOT, manifest)
        self.assertEqual([], result["findings"], result["findings"][:5])
        self.assertGreaterEqual(len(manifest["consolidation"]["deletedPaths"]), 56)


class SyntheticTree(unittest.TestCase):
    def setUp(self) -> None:
        self.scratch = Path(tempfile.mkdtemp(prefix="stale-paths-", dir=_runtime_root()))
        self.manifest = MODULE.load_manifest(MANIFEST)
        # The live allowances name live files; a scratch tree without them would report
        # ALLOWANCE_UNMET for every case and blur which finding is under test.
        self.manifest["allowances"] = []
        self._files = []
        self._tracked = MODULE.tracked_files
        MODULE.tracked_files = lambda root: list(self._files)

    def tearDown(self) -> None:
        MODULE.tracked_files = self._tracked
        shutil.rmtree(self.scratch, ignore_errors=True)

    def _write(self, rel: str, text: str) -> None:
        path = self.scratch / rel
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text, encoding="utf-8")
        self._files.append(rel)

    def test_a_planted_old_path_on_an_active_surface_is_convicted(self) -> None:
        self._write("docs/current/POINTER.md",
                    "接手指令见 taskpacks/current/ORCA-PILOT-TASK-CARD-20260925.md\n")
        result = MODULE.scan(self.scratch, self.manifest)
        self.assertEqual([], result["allowanceFailures"])
        self.assertTrue(any(f.startswith("STALE docs/current/POINTER.md:1")
                            and "ORCA-PILOT-TASK-CARD-20260925.md" in f
                            for f in result["findings"]), result["findings"])

    def test_a_planted_old_directory_prefix_is_convicted(self) -> None:
        self._write(".project/governance/pointer.json",
                    '{"x": "docs/current/ui-priority-20261009/anything.md"}\n')
        result = MODULE.scan(self.scratch, self.manifest)
        self.assertTrue(any("STALE .project/governance/pointer.json:1" in f
                            for f in result["findings"]), result["findings"])

    def test_a_planted_reference_to_a_deleted_archive_member_is_convicted(self) -> None:
        """The second half of the owner's instruction: nothing may index onto deleted material.

        The move record's `from` paths say where a document used to live; the consolidation's
        `deletedPaths` say where it lived just before being deleted. A pointer to either is the same
        defect, so both are enforced by one matcher.
        """
        sample = MODULE.load_manifest(MANIFEST)["consolidation"]["deletedPaths"][0]
        self._write("docs/current/POINTER.md", f"接手指令见 {sample}\n")
        result = MODULE.scan(self.scratch, self.manifest)
        self.assertTrue(any(f.startswith("STALE docs/current/POINTER.md:1") and sample in f
                            for f in result["findings"]), result["findings"][:3])

    def test_a_frozen_original_tree_spelling_is_not_convicted(self) -> None:
        """The guard that makes the whole scope survivable: history keeps its own operands.

        This is the regression test for the alternation bug. `(?<!x)a|b|c` parses as
        `((?<!x)a)|b|c`, so one lookbehind guarded only the first of 48 alternatives and every
        `original-tree` archivePath in the taskpack index read as stale.
        """
        frozen = ("taskpacks/history/UI-PRIORITY-CUTOVER-20261009/original-tree/"
                  "taskpacks/current/ORCA-PILOT-TASK-CARD-20260925.md")
        self._write("docs/audits/RECORD.md", f"引用 {frozen}\n")
        result = MODULE.scan(self.scratch, self.manifest)
        self.assertEqual([], result["findings"],
                         "a frozen original-tree path must never be called stale")

    def test_history_and_evidence_roots_are_out_of_scope(self) -> None:
        for rel in ("docs/history/archive/RECORD.md", "taskpacks/history/OLD.md",
                    "reports/audit-evidence/R.md", "knowledge-staging/x/SKILL.md",
                    ".workbuddy/note.md"):
            self._write(rel, "taskpacks/current/ORCA-PILOT-TASK-CARD-20260925.md\n")
        self._write("docs/current/LIVE.md", "taskpacks/current/ORCA-PILOT-TASK-CARD-20260925.md\n")
        result = MODULE.scan(self.scratch, self.manifest)
        self.assertEqual(1, len(result["findings"]), result["findings"])
        self.assertTrue(result["findings"][0].startswith("STALE docs/current/LIVE.md"), result["findings"])

    def test_an_allowance_that_stops_being_used_fails(self) -> None:
        """Renaming the last stale pointer away must reopen the licence, not pass silently."""
        self.manifest["allowances"] = [{"path": "README.md", "reason": "declared but nothing to allow",
                                        "minOccurrences": 1}]
        self._write("README.md", "clean text\n")
        result = MODULE.scan(self.scratch, self.manifest)
        self.assertEqual([], result["findings"])
        self.assertTrue(any(f.startswith("ALLOWANCE_UNMET README.md") for f in
                            result["allowanceFailures"]), result["allowanceFailures"])

    def test_the_manifest_itself_is_not_scanned(self) -> None:
        """The move record names every old path; convicting its own file would be nonsense."""
        self._write("docs/history/archive/MOVED-PATHS-20261019.json",
                    json.dumps({"moves": []}))
        self.assertIn("docs/history/archive/MOVED-PATHS-20261019.json",
                      [x for x in self._files])
        self.assertFalse(MODULE.in_scope("docs/history/archive/MOVED-PATHS-20261019.json",
                                         self.manifest))

    def test_a_binary_file_cannot_hide_a_stale_pointer_or_crash_the_scan(self) -> None:
        self._write("apps/observer/blob.dat", "taskpacks/current/ORCA-PILOT-TASK-CARD-20260925.md\n")
        (self.scratch / "apps/observer/blob.dat").write_bytes(b"\xff\xfe\x00 binary\n")
        result = MODULE.scan(self.scratch, self.manifest)
        self.assertEqual([], result["findings"],
                         "undecodable bytes are skipped, they are not a failure of the instrument")


class ManifestShape(unittest.TestCase):
    def test_every_allowance_carries_a_reason_and_a_minimum(self) -> None:
        manifest = MODULE.load_manifest(MANIFEST)
        self.assertGreaterEqual(len(manifest["allowances"]), 4)
        for entry in manifest["allowances"]:
            self.assertTrue(len(entry.get("reason", "")) > 40, entry)
            self.assertGreaterEqual(entry.get("minOccurrences", 0), 1, entry)
            self.assertTrue((ROOT / entry["path"]).is_file(), f"allowance names a missing file: {entry}")

    def test_the_directive_is_recorded_verbatim(self) -> None:
        """The move is justified by an owner decision, so the decision itself is the evidence."""
        manifest = MODULE.load_manifest(MANIFEST)
        for fragment in ("旧的过时的冗余的陈旧的", "全部归档到该去汇总的地方", "防止再次索引路径到旧资料上"):
            self.assertIn(fragment, manifest["directive"], fragment)


class ArchivePreconditionIsNamed(unittest.TestCase):
    def test_an_unfetched_lfs_object_is_named_instead_of_crashing_the_zip_reader(self) -> None:
        """Planted pointer bytes: the guard must fire with its own name, never as a BadZipFile.

        Measured on the 2026-10-20 exact-SHA run, where one missing precondition surfaced as three separate
        findings -- two tracebacks and a hash mismatch -- and the reader had to reconstruct the cause from
        the wreckage instead of reading it.
        """
        fake = _runtime_root() / "lfs-pointer-probe.zip"
        fake.write_bytes(b"version https://git-lfs.github.com/spec/v1\noid sha256:"
                         + b"0" * 64 + b"\nsize 268142\n")
        try:
            with self.assertRaises(AssertionError) as caught:
                open_archive(fake)
            self.assertIn("LFS_NOT_FETCHED", str(caught.exception), str(caught.exception))
        finally:
            fake.unlink()

    def test_a_missing_archive_is_reported_as_missing(self) -> None:
        fake = _runtime_root() / "archive-that-was-never-written.zip"
        fake.unlink(missing_ok=True)
        with self.assertRaises(AssertionError) as caught:
            open_archive(fake)
        self.assertIn("ARCHIVE_MISSING", str(caught.exception), str(caught.exception))


if __name__ == "__main__":
    unittest.main()

# SPDX-License-Identifier: MIT
"""The hermes migration verifier audited a gitignored archive and had been red for weeks.

Measured 2026-10-09: `--verify` had been invoked by no CI table, no aggregate entry and no test,
and it printed FAIL in both trees. Its complaint was half real and half stale. Real: 108 of 109
archived objects are present with unchanged digests and no source was left behind. Stale: the one
absent object (`.project-local/archive/hermes-legacy/runtime/dl-ad-pkg-ci`, 253.3 MB, 5559 files)
was deleted on 2026-09-26 **in a tracked record** -- `prune-manifest-2026-09-26.json`
`phase2.removed[0]` and the closeout ledger §C, both dated, both saying it was a CI-reproducible
build artefact. The verifier's premise never learned about a later recorded deletion, so it could
only ever be wrong, and being uninvoked is what made that survivable.

The split asserted here: the manifest is audited from its versioned copy, a gone object must be
named by a versioned removal record, and whether this machine still holds the archive is reported,
never required.
"""
from __future__ import annotations

import io
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "scripts"))

import deepseek_hermes_migration as tool  # noqa: E402

MANIFEST_REL = "docs/audits/DESIGN-LAB-UIKIT-CONFORMANCE-2026-09-28/session/hermes-legacy/MIGRATION-MANIFEST.json"
PRUNE_REL = ("docs/audits/DESIGN-LAB-UIKIT-CONFORMANCE-2026-09-28/evidence/governance-state/"
             "prune-manifest-2026-09-26.json")
REMOVED_TARGET = ".project-local/archive/hermes-legacy/runtime/dl-ad-pkg-ci"


def manifest() -> dict:
    return json.loads((ROOT / MANIFEST_REL).read_text(encoding="utf-8"))


class VersionedInputTests(unittest.TestCase):
    def test_both_records_the_verdict_needs_are_in_git(self) -> None:
        tracked = set(subprocess.run(["git", "-C", str(ROOT), "ls-files"], capture_output=True,
                                     text=True, encoding="utf-8", errors="replace").stdout.split())
        self.assertIn(MANIFEST_REL, tracked)
        self.assertIn(PRUNE_REL, tracked)

    def test_the_archived_copy_still_equals_the_live_manifest_where_it_exists(self) -> None:
        live = ROOT / ".project-local/archive/hermes-legacy/MIGRATION-MANIFEST.json"
        if not live.is_file():
            self.skipTest("no hermes archive on this machine; the tracked copy is what is audited")
        self.assertEqual(live.read_bytes(), (ROOT / MANIFEST_REL).read_bytes())

    def test_the_recorded_removal_set_is_exactly_the_2026_09_26_prune_entry(self) -> None:
        removals = tool.recorded_removals()
        self.assertEqual(sorted(removals), [REMOVED_TARGET],
                         "the set of recorded archive removals moved; a deletion must be written "
                         "in the prune record or the verifier must fail")
        self.assertGreater(len(removals[REMOVED_TARGET]["reason"]), 5,
                           "a removal without a stated reason is a disappearance, not a record")
        self.assertTrue(removals[REMOVED_TARGET]["pruned_at"])


class ManifestShapeTests(unittest.TestCase):
    def test_the_shipped_manifest_passes_the_tracked_checks(self) -> None:
        document = manifest()
        self.assertEqual(tool.manifest_findings(document, document["records"],
                                                tool.recorded_removals()), [])
        self.assertEqual(len(document["records"]), 109)

    def planted(self, mutate) -> list[str]:
        document = manifest()
        mutate(document)
        return tool.manifest_findings(document, document["records"], tool.recorded_removals())

    def test_a_source_outside_the_legacy_roots_is_convicted(self) -> None:
        findings = self.planted(lambda d: d["records"][0].__setitem__("source", "src/whatever.py"))
        self.assertTrue(any("outside the legacy roots" in line for line in findings), findings)

    def test_an_archive_target_outside_the_hermes_root_is_convicted(self) -> None:
        findings = self.planted(lambda d: d["records"][0].__setitem__(
            "target", ".project-local/quarantine/elsewhere"))
        self.assertTrue(any("archives outside the hermes-legacy root" in line
                            for line in findings), findings)

    def test_a_duplicated_target_is_convicted_because_two_datasets_would_merge(self) -> None:
        def mutate(document):
            document["records"][1] = dict(document["records"][0])
        findings = self.planted(mutate)
        self.assertTrue(any("appears twice" in line for line in findings), findings)

    def test_a_record_without_a_verifiable_digest_is_convicted(self) -> None:
        for bad in ("", "sha256:deadbeef", None, "622442d2"):
            findings = self.planted(lambda d, b=bad: d["records"][0].__setitem__(
                "verified_digest", b))
            self.assertTrue(any("no digest a restore could be verified against" in line
                                for line in findings), (bad, findings))

    def test_a_restore_note_that_does_not_name_where_bytes_go_is_convicted(self) -> None:
        findings = self.planted(lambda d: d["records"][0].__setitem__("restore", "restore it"))
        self.assertTrue(any("does not say where the bytes go back" in line
                            for line in findings), findings)

    def test_an_empty_looking_record_with_no_content_is_convicted(self) -> None:
        findings = self.planted(lambda d: d["records"][0].update({"files": 0, "bytes": 0}))
        self.assertTrue(any("neither files nor bytes" in line for line in findings), findings)

    def test_a_manifest_from_a_different_contract_is_convicted(self) -> None:
        findings = self.planted(lambda d: d.__setitem__("schemaVersion", "other/v1"))
        self.assertTrue(any("not the migration manifest contract" in line
                            for line in findings), findings)
        findings = self.planted(lambda d: d.__setitem__(
            "restore_command", "python scripts/deepseek_hermes_migration.py --apply"))
        self.assertTrue(any("not this tool's documented --restore form" in line
                            for line in findings), findings)

    def test_a_removal_that_no_migration_record_describes_is_convicted(self) -> None:
        document = manifest()
        removals = tool.recorded_removals()
        removals[".project-local/archive/hermes-legacy/runtime/invented"] = {
            "reason": "(1MB, whatever)", "pruned_at": "2026-09-26", "entry": "x"}
        findings = tool.manifest_findings(document, document["records"], removals)
        self.assertTrue(any("no migration record describes that object" in line
                            for line in findings), findings)


class ArchiveStateTests(unittest.TestCase):
    """`verify()` driven against a throwaway tree, so a missing object can be planted."""

    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.tmp = Path(self._tmp.name)
        self.saved = (tool.REPO, tool.ARCHIVE, tool.TRACKED_MANIFEST, tool.PRUNE_RECORD)
        (self.tmp / MANIFEST_REL).parent.mkdir(parents=True)
        (self.tmp / MANIFEST_REL).write_bytes((ROOT / MANIFEST_REL).read_bytes())
        (self.tmp / PRUNE_REL).parent.mkdir(parents=True, exist_ok=True)
        (self.tmp / PRUNE_REL).write_bytes((ROOT / PRUNE_REL).read_bytes())
        tool.REPO = self.tmp
        tool.ARCHIVE = self.tmp / ".project-local/archive/hermes-legacy"
        tool.TRACKED_MANIFEST = self.tmp / MANIFEST_REL
        tool.PRUNE_RECORD = self.tmp / PRUNE_REL

    def tearDown(self) -> None:
        tool.REPO, tool.ARCHIVE, tool.TRACKED_MANIFEST, tool.PRUNE_RECORD = self.saved
        self._tmp.cleanup()

    def capture(self) -> tuple[int, str]:
        import io
        from contextlib import redirect_stdout
        buffer = io.StringIO()
        with redirect_stdout(buffer):
            code = tool.verify()
        return code, buffer.getvalue()

    def test_a_tree_with_no_archive_reports_absent_instead_of_deleting_the_claim(self) -> None:
        code, output = self.capture()
        self.assertEqual(code, 0, output)
        self.assertIn("archive=ABSENT_ON_THIS_MACHINE", output)
        self.assertIn("MIGRATION_VERIFY=PASS", output)
        self.assertIn("objects=109", output)

    def test_an_empty_archive_convicts_every_object_the_prune_record_does_not_name(self) -> None:
        tool.ARCHIVE.mkdir(parents=True)
        code, output = self.capture()
        self.assertEqual(code, 1, "an archive that vanished must not read as clean")
        self.assertIn("archive=MEASURED_ON_THIS_MACHINE", output)
        missing = [line for line in output.splitlines() if "missing target" in line]
        self.assertEqual(len(missing), 108, len(missing))
        self.assertNotIn(REMOVED_TARGET, output,
                         "the one removal that IS recorded must not be counted as a loss")

    def test_a_restored_object_with_changed_bytes_is_convicted(self) -> None:
        tool.ARCHIVE.mkdir(parents=True)
        record = manifest()["records"][0]
        target = tool.REPO / record["target"]
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text("not what was archived\n", encoding="utf-8", newline="\n")
        code, output = self.capture()
        self.assertEqual(code, 1)
        self.assertIn("digest changed", output)

    def test_a_source_left_behind_alongside_its_copy_is_convicted(self) -> None:
        tool.ARCHIVE.mkdir(parents=True)
        record = manifest()["records"][0]
        target = tool.REPO / record["target"]
        target.parent.mkdir(parents=True, exist_ok=True)
        # The target has to exist for the source half of the claim to be reached at all, so this
        # plant writes both: the failure under test is the leftover original, not the digest.
        target.write_text("archived bytes\n", encoding="utf-8", newline="\n")
        source = tool.REPO / record["source"]
        source.parent.mkdir(parents=True, exist_ok=True)
        source.write_text("x", encoding="utf-8", newline="\n")
        code, output = self.capture()
        self.assertEqual(code, 1)
        self.assertIn("source still present", output)


class RuntimeTests(unittest.TestCase):
    def test_the_shipped_verify_passes_here_and_writes_nothing(self) -> None:
        def porcelain() -> str:
            return subprocess.run(["git", "status", "--porcelain"], cwd=str(ROOT),
                                  capture_output=True, text=True, encoding="utf-8",
                                  errors="replace").stdout

        before = porcelain()
        result = subprocess.run([sys.executable, "-X", "utf8", "-B",
                                 str(ROOT / "scripts" / "deepseek_hermes_migration.py"), "--verify"],
                                cwd=str(ROOT), capture_output=True, text=True,
                                encoding="utf-8", errors="replace", timeout=900)
        output = (result.stdout or "") + (result.stderr or "")
        self.assertEqual(result.returncode, 0, output[-900:])
        self.assertIn("MIGRATION_VERIFY=PASS", output)
        self.assertIn("recorded_removals=1", output)
        self.assertEqual(before, porcelain(), "--verify wrote a tracked file")


if __name__ == "__main__":
    unittest.main()

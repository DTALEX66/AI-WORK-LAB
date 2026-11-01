"""Gate: a tracked document may not cite an absent `.project-local` evidence path without a disposition.

The auditable claim is not "how many absent paths are there" (that number is an artefact of the
scanner's scope: 28 from one pass, 200 tokens from a full-tree pass). It is the narrower one this
gate protects — every path that survives classification as a possible unavailable-evidence claim
must carry a hand-written disposition, so a reader is never sent to bytes that are not there.

Negative controls feed the classifier the exact sentence shapes that shipped so its buckets cannot
rot: an instruction to create a file must not be confused with a claim that the file is evidence.
"""
from __future__ import annotations

import importlib.util
import json
import subprocess
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SCRIPT = ROOT / "scripts" / "audit" / "project_local_citation_audit.py"
AUDIT = ROOT / "docs" / "audits" / "PROJECT_LOCAL_CITATION_AUDIT_2026-10-07.json"
IMPORT_ROOT = (ROOT / ".project-local" / "imported-from-workbuddy-20261006" /
               "WORK-LAB__task-decomposition-atlas-gap-archive-20261001-381e33ec")

spec = importlib.util.spec_from_file_location("plca", SCRIPT)
plca = importlib.util.module_from_spec(spec)
spec.loader.exec_module(plca)

REVIEW_CLASSES = ("machine_field_pointing_at_absent_path", "unclassified_needs_human_read")


def classify(line: str, file: str = "docs/current/some-doc.md",
             token: str = ".project-local/runs/x/receipt.json") -> str:
    return plca.classify(token, file, line)


class CitationAuditGate(unittest.TestCase):
    def test_shipped_audit_exists_and_is_the_current_schema(self) -> None:
        doc = json.loads(AUDIT.read_text(encoding="utf-8"))
        self.assertEqual(doc["schemaVersion"], "work-lab/project-local-citation-audit/v2")
        self.assertGreater(doc["scope"]["trackedFilesScanned"], 1500)

    def test_every_queued_path_has_a_disposition(self) -> None:
        doc = json.loads(AUDIT.read_text(encoding="utf-8"))
        unadjudicated = [p for p, d in doc["dispositions"].items() if d == "UNADJUDICATED"]
        self.assertEqual(unadjudicated, [], "queued citations without a per-path disposition")
        self.assertEqual(doc["counts"]["unadjudicated"], 0)

    def test_the_repair_names_the_import_root_that_the_register_records(self) -> None:
        # CI checks the tracked records agree; whether the bytes are still on this machine is a
        # local observation, because .project-local is git-ignored and absent from a fresh checkout.
        # The live file is now a FROZEN_ARCHIVED pointer whose own text names this original and its SHA-256
        # (693b2f72…), so the guard follows the record to the bytes it describes instead of loosening itself.
        handoff = (ROOT / "taskpacks/history/UI-PRIORITY-CUTOVER-20261009/original-tree"
                   / "taskpacks/current/SESSION-HANDOFF-P0C-20261006.md") \
            .read_text(encoding="utf-8")
        rows = [ln for ln in (ROOT / "taskpacks/history/UI-PRIORITY-CUTOVER-20261009/original-tree"
                              / "taskpacks/current/OPEN-TASK-REGISTER.md")
                .read_text(encoding="utf-8").splitlines()
                if ln.startswith("| WB-IMPORT-20261006 ")]
        # The live register became the UI-priority WUI table on 2026-10-09, so the import round it used to
        # carry now lives in the frozen original tree this guard reads (LEGACY-TASK-DISPOSITION.json records
        # the per-row inheritance). Read from the file that holds the claim, do not drop the claim's guard.
        self.assertEqual(len(rows), 1, "the import round is no longer a single register row")
        for token in ("imported-from-workbuddy-20261006", "381e33ec"):
            self.assertIn(token, handoff, token)
            self.assertIn(token, rows[0], token)
        self.assertIn("runs/p0c-diag-20261006", handoff)
        self.assertTrue((ROOT / "taskpacks" / "current" / "error-ledger.json").is_file())

    @unittest.skipUnless(IMPORT_ROOT.is_dir(),
                         "the WorkBuddy import sits in the git-ignored runtime root; a clean CI "
                         "checkout has no .project-local, so only the machine holding it can "
                         "observe the bytes")
    def test_the_re_pointed_bytes_are_present_on_the_machine_that_holds_them(self) -> None:
        diag = IMPORT_ROOT / ".project-local" / "runs" / "p0c-diag-20261006"
        self.assertTrue(diag.is_dir(), "the re-pointed evidence root is not on disk")
        self.assertGreater(len(list(diag.iterdir())), 10)

    def test_an_evidence_citation_to_an_absent_path_reaches_the_review_queue(self) -> None:
        self.assertIn(classify("复现命令（证据在 `.project-local/runs/x/receipt.json`）："), REVIEW_CLASSES)
        self.assertIn(classify('see .project-local/runs/x/receipt.json for the full capture'),
                      REVIEW_CLASSES)

    def test_a_declared_destination_is_not_an_evidence_claim(self) -> None:
        self.assertEqual(classify('DEFAULT_OUT = Path(".project-local/runs/x/receipt.json")',
                                 "scripts/ci/x.py"),
                         "declared_output_destination_or_fixture_in_code")
        self.assertEqual(classify("python audit.py --output .project-local/runs/x/receipt.json"),
                         "declared_output_destination_or_fixture_in_code")

    def test_a_removal_record_is_not_an_evidence_claim(self) -> None:
        self.assertEqual(classify("deleted: this path must not exist after cleanup"),
                         "negative_assertion_or_removal_record")
        self.assertEqual(classify("legacy isolated-checkout layout, no longer used"),
                         "negative_assertion_or_removal_record")

    def test_a_placeholder_never_counts_as_one_missing_file(self) -> None:
        self.assertEqual(classify("writes .project-local/runs/probe-202XX.json",
                                  token=".project-local/runs/probe-202XX.json"),
                         "path_pattern_or_truncated_token")

    def test_the_scanner_is_not_vacuous_on_this_tree(self) -> None:
        # an empty bucket table would make every assertion above pass by accident
        doc = json.loads(AUDIT.read_text(encoding="utf-8"))
        self.assertGreaterEqual(len(doc["countsByClass"]), 5)
        self.assertGreaterEqual(sum(v["citations"] for v in doc["countsByClass"].values()), 150)
        # the queue shrank by design when the machine-local classes were declared (ERR-142): it went
        # 148 -> 57 -> 6 as runtime-root pointers stopped being adjudicated path by path. The floor is
        # therefore the new one, and the two declared buckets are guarded so nobody empties them and
        # calls the resulting quiet a clean tree.
        self.assertGreaterEqual(len(doc["unavailableEvidenceReviewQueue"]), 5)
        classes = {k: v for k, v in doc["countsByClass"].items()}
        self.assertGreaterEqual(classes.get("machine_local_runtime_pointer", {}).get("citations", 0),
                                100, "the declared machine-local class went quiet; that is not a fix")
        self.assertGreaterEqual(
            classes.get("machine_local_runtime_narration", {}).get("citations", 0), 400,
            "the narration class went quiet; the classifier order changed silently")


    def test_a_runtime_root_path_is_never_treated_as_checkout_verifiable(self) -> None:
        """The rule that made the verdict machine-independent (ERR-142).

        `.project-local/artifacts/model-library-readback.json` really exists on the box that wrote the
        records. If `exists()` ever answers True for it, the queue grows on one machine and shrinks on
        another, and CI fails on the author's own tooling — which is exactly what happened at c53de17.
        """
        real = ".project-local/artifacts/model-library-readback.json"
        self.assertFalse(plca.exists(real),
                         "the runtime root became machine-dependent again: exists() must answer from "
                         "the repository, never from this box")
        self.assertTrue(plca.exists("README.md"), "tracked verification broke; the audit is now blind")
        doc = json.loads(AUDIT.read_text(encoding="utf-8"))
        self.assertEqual(doc["counts"]["checkoutVerifiable"], 0,
                         "the shipped record claims something under the git-ignored root is "
                         "checkout-verifiable, which is the machine-dependence ERR-142 removed")

    def test_the_record_never_scans_itself(self) -> None:
        """Self-exclusion, because a record that quotes its own findings is a feedback loop.

        Before the exclusion the audit's own JSON was part of the corpus, so every regeneration
        re-scanned the citations it had just written and the file grew 1.7 MB -> 3.7 MB in one pass,
        while the adjudicated state (22 queued / 0 unadjudicated) did not change at all.
        """
        doc = json.loads(AUDIT.read_text(encoding="utf-8"))
        citing = {c["file"] for bucket in doc["buckets"].values() for c in bucket}
        self.assertNotIn(AUDIT.relative_to(ROOT).as_posix(), citing,
                         "the audit scanned its own output")
        self.assertFalse(any("PROJECT_LOCAL_CITATION_AUDIT" in f for f in citing),
                         "a citation in the record originates from the record itself")
        self.assertNotIn("PROJECT_LOCAL_CITATION_AUDIT",
                         json.dumps(doc["unavailableEvidenceReviewQueue"]))

    def test_regenerating_the_record_is_idempotent_apart_from_the_timestamp(self) -> None:
        """Two passes over the same tree must agree.

        Not compared against the shipped record: a scratch run does not exclude the shipped record
        from its corpus, so it legitimately quotes the citations that record carries. Equality with
        the shipped state is asserted by the record-agreement test above.
        """
        scratch = ROOT / ".project-local" / "runs" / "citation-audit-selftest"
        scratch.mkdir(parents=True, exist_ok=True)
        outs = []
        for name in ("first.json", "second.json"):
            target = scratch / name
            proc = subprocess.run([sys.executable, str(SCRIPT), "--out", str(target)], cwd=ROOT,
                                  capture_output=True, text=True, encoding="utf-8", errors="replace")
            # the exit code is a governance state (unadjudicated -> 1), not a property of this test, so
            # determinism is asserted on the record's own counts instead of on the wrapper status
            self.assertEqual(proc.returncode, 0, proc.stdout + proc.stderr)
            body = json.loads(target.read_text(encoding="utf-8"))
            self.assertEqual(body["counts"]["unadjudicated"], 0,
                             f"the audit is not machine-independent any more: {body['counts']}")
            body.pop("generatedAt")
            outs.append(body)
        self.assertEqual(outs[0], outs[1], "two passes over the same tree disagreed")
        # Only the checkout-deterministic counts are compared against the shipped record.
        deterministic = ("reviewQueue", "unadjudicated", "checkoutVerifiable")
        shipped = json.loads(AUDIT.read_text(encoding="utf-8"))
        self.assertEqual({k: outs[0]["counts"][k] for k in deterministic},
                         {k: shipped["counts"][k] for k in deterministic},
                         "a fresh scan disagrees with the shipped record about the adjudicated state")
        # `presentOnThisMachine` is reported, never compared. It counts citation tokens whose bytes the
        # running box happens to hold under the git-ignored root, so it moves with the disk: a clean
        # checkout showed 10 against 174 here, and it also self-amplifies, because this very test writes
        # first.json/second.json into `.project-local/runs/` before re-scanning. Any bound on it —
        # equality *or* >= — is a gate that decays with the machine, which is the ERR-142 failure class.
        for doc in (outs[0], shipped):
            value = doc["counts"]["presentOnThisMachine"]
            self.assertIsInstance(value, int)
            self.assertGreaterEqual(value, 0)


if __name__ == "__main__":
    unittest.main(verbosity=2)

"""Gate: archived native evidence must name the commit it describes, and the job must upload it.

Why this exists: the exe receipt was written into `apps/observer/src-tauri/target/` (a cache the workflow
restores and never uploads) and the native readback into `.project-local/runs/` (not in the upload list),
so CI's "native acceptance evidence" existed only as long as the runner's cache did, and nothing in the
bytes said which commit they described. An archived verdict that cannot name its commit can be reused
across commits, which is the same defect the WUI evidence seal was written for.

The stale-artifact control is the point: feed the archiver a receipt whose `gitHead` differs from the
commit being verified and it must refuse. The wiring control matters just as much -- an instrument no job
executes and an artifact no job uploads are descriptions of a gate, not a gate -- so the observer job's
step list and upload list are read back from the workflow file here.
"""
from __future__ import annotations

import importlib.util
import json
import os
import re
import sys
import unittest
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parents[2]
SCRIPT = ROOT / "apps" / "observer" / "scripts" / "write_artifact_receipt.py"
U19_SCRIPT = ROOT / "apps" / "observer" / "scripts" / "u19_webview_e2e.py"
WORKFLOW = ROOT / ".github" / "workflows" / "work-lab-gate.yml"
PROJECT_TEMP = ROOT / "packages" / "client-neutral-core" / "scripts" / "project_temp.py"

_spec = importlib.util.spec_from_file_location("write_artifact_receipt_under_test", SCRIPT)
wr = importlib.util.module_from_spec(_spec)
assert _spec.loader is not None
_spec.loader.exec_module(wr)  # type: ignore[attr-defined]

_u19_spec = importlib.util.spec_from_file_location("u19_webview_e2e_for_evidence", U19_SCRIPT)
u19 = importlib.util.module_from_spec(_u19_spec)
assert _u19_spec.loader is not None
sys.path.insert(0, str(ROOT / "apps" / "observer" / "scripts"))
_u19_spec.loader.exec_module(u19)  # type: ignore[attr-defined]

_pt_spec = importlib.util.spec_from_file_location("project_temp_for_evidence", PROJECT_TEMP)
project_temp = importlib.util.module_from_spec(_pt_spec)
assert _pt_spec.loader is not None
_pt_spec.loader.exec_module(project_temp)  # type: ignore[attr-defined]

HEAD_A = "a" * 40
HEAD_B = "b" * 40
EXE_SHA = "c" * 64


def payload(git_head: str = HEAD_A, exe_sha: str = EXE_SHA) -> dict:
    return {"schemaVersion": wr.RECEIPT_SCHEMA, "gitHead": git_head,
            "binary": {"path": "apps/observer/src-tauri/target/release/app.exe",
                       "bytes": 7, "sha256": exe_sha},
            "inputCount": 1, "inputs": [], "frontendInputCount": 0, "frontendInputs": []}


def build_tree(root: Path) -> tuple[Path, Path]:
    """The layout `write_receipt()` hashes, minimally, inside a bounded fixture root."""
    obs = root / "apps" / "observer"
    (obs / "src-tauri" / "src").mkdir(parents=True, exist_ok=True)
    (obs / "src-tauri" / "src" / "lib.rs").write_text("fn main() {}\n", encoding="utf-8")
    (obs / "frontend" / "dist").mkdir(parents=True, exist_ok=True)
    (obs / "frontend" / "dist" / "index.html").write_text("<html>built</html>\n", encoding="utf-8")
    exe = obs / "src-tauri" / "target" / "release" / "app.exe"
    exe.parent.mkdir(parents=True, exist_ok=True)
    exe.write_bytes(b"binary!")
    return obs, exe


class ArchiveNamingTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = project_temp.fixture_dir(prefix="wl-native-evidence-")

    def tearDown(self) -> None:
        if not project_temp.force_release(self.tmp):
            self.fail(f"fixture root was not released: {self.tmp}")

    def test_the_archived_name_carries_the_commit_and_the_exe_digest(self) -> None:
        out = wr.archive_native_evidence(self.tmp, "app-receipt", payload())
        self.assertEqual(f"app-receipt.g{HEAD_A[:12]}.x{EXE_SHA[:16]}.inputs.json", out.name)
        stored = json.loads(out.read_text(encoding="utf-8"))
        self.assertEqual(HEAD_A, stored["gitHead"])
        self.assertEqual(HEAD_A[:12], stored["commitPrefix"])
        self.assertEqual(EXE_SHA, stored["binary"]["sha256"])

    def test_a_receipt_that_names_no_commit_is_refused_not_archived(self) -> None:
        with self.assertRaises(SystemExit) as refused:
            wr.archive_native_evidence(self.tmp, "app-receipt", payload(git_head="UNKNOWN"))
        self.assertIn("WRITE_RECEIPT_ARCHIVE_REFUSED", str(refused.exception))
        self.assertFalse((self.tmp / wr.NATIVE_EVIDENCE_DIR).exists(),
                         "a refused archive must not leave a directory behind")

    def test_the_verifier_accepts_evidence_that_names_the_commit(self) -> None:
        wr.archive_native_evidence(self.tmp, "app-receipt", payload())
        self.assertEqual([], wr.verify_native_evidence(self.tmp, HEAD_A))

    def test_the_verifier_refuses_a_receipt_from_a_different_commit(self) -> None:
        """The stale-artifact control: yesterday's verdict must not answer for today's tree."""
        wr.archive_native_evidence(self.tmp, "app-receipt", payload(git_head=HEAD_A))
        problems = wr.verify_native_evidence(self.tmp, HEAD_B)
        self.assertTrue(problems, "a receipt for another commit was accepted as current")
        self.assertIn(HEAD_B[:12], " ".join(problems))

    def test_the_verifier_refuses_an_artifact_whose_name_and_payload_disagree(self) -> None:
        wr.archive_native_evidence(self.tmp, "app-receipt", payload(git_head=HEAD_A))
        forged = self.tmp / wr.NATIVE_EVIDENCE_DIR
        target = next(forged.glob("app-receipt.*"))
        document = json.loads(target.read_text(encoding="utf-8"))
        document["gitHead"] = HEAD_B
        target.write_text(json.dumps(document), encoding="utf-8")
        problems = wr.verify_native_evidence(self.tmp, HEAD_B)
        self.assertTrue(any("does not describe" in p for p in problems), problems)

    def test_the_verifier_refuses_an_unbound_or_unreadable_artifact(self) -> None:
        out_dir = self.tmp / wr.NATIVE_EVIDENCE_DIR
        out_dir.mkdir(parents=True, exist_ok=True)
        (out_dir / "loose-receipt.inputs.json").write_text(json.dumps(payload()), encoding="utf-8")
        problems = wr.verify_native_evidence(self.tmp, HEAD_A)
        self.assertTrue(any("naming rule" in p for p in problems), problems)
        (out_dir / "broken.inputs.json").write_text("{not json", encoding="utf-8")
        self.assertTrue(any("unreadable" in p for p in
                            wr.verify_native_evidence(self.tmp, HEAD_A)))

    def test_an_empty_archive_is_refused_rather_than_passing(self) -> None:
        self.assertTrue(wr.verify_native_evidence(self.tmp, HEAD_A))
        (self.tmp / wr.NATIVE_EVIDENCE_DIR).mkdir(parents=True, exist_ok=True)
        self.assertTrue(any("no archived native evidence describes commit" in problem
                            for problem in wr.verify_native_evidence(self.tmp, HEAD_A)))

    def test_a_non_commit_expectation_is_refused(self) -> None:
        for bad in ("", "UNKNOWN", None):
            self.assertTrue(wr.verify_native_evidence(self.tmp, bad or ""),
                            f"verify accepted a head that names nothing: {bad!r}")

    def test_the_writer_archives_alongside_the_build_output(self) -> None:
        obs, exe = build_tree(self.tmp)
        with mock.patch.object(wr, "git_head", lambda root: HEAD_A):
            receipt = wr.write_receipt(self.tmp, obs, exe)
        self.assertTrue(Path(receipt["receiptPath"]).is_file(),
                        "the compiler-side receipt still has to sit next to the binary")
        archived = Path(receipt["archivedReceiptPath"])
        self.assertTrue(archived.is_file())
        self.assertIn(f".project-local{os.sep}artifacts", str(archived.parent))
        self.assertEqual([], wr.verify_native_evidence(self.tmp, HEAD_A))


class WorkflowWiringTests(unittest.TestCase):
    """Every instrument this fix touches has to be executed and uploaded by a job."""

    @classmethod
    def setUpClass(cls) -> None:
        cls.text = WORKFLOW.read_text(encoding="utf-8")

    def step_block(self, name_fragment: str) -> str:
        blocks = re.split(r"\n      - (?=name: |uses: )", self.text)
        matches = [block for block in blocks if name_fragment in block.splitlines()[0]]
        self.assertTrue(matches, f"no workflow step is named {name_fragment!r}; the wiring is a claim")
        return "\n".join(matches)

    def test_the_window_state_readback_is_executed_and_declared_reported_only(self) -> None:
        """Executed on every run, its verdict published, and its contract written next to it.

        What changed on 2026-10-26 is the *contract*, not the measurement: the runner cannot show a window
        (`display` PASS, `draw` PASS, `visible_desktop` unresolved, every app window `visible=false`, no CDP
        page target), so a native window-state proof is unobtainable there and the step may not gate the
        pull request. Non-gating is only honest while it is declared, so this asserts the declaration exists
        in the file and that the step is still executed with its artifact path -- deleting either is red.
        What used to be asserted here (`not continue-on-error`) pinned strictness itself, which meant the
        environment could not be reported as a limit without turning the whole job red.
        """
        block = self.step_block("Window state readback")
        self.assertIn("apps/observer/scripts/window_state_readback.py", block)
        self.assertIn("--json-out .project-local/runs/ci/window_state_readback.json", block)
        self.assertIn("continue-on-error: true", block,
                      "the step must not gate the verdict any more -- but only as declared below")
        for phrase in ("NOT REQUIRED", "visible_desktop"):
            self.assertIn(phrase, block,
                          f"the step lost the words that make it a declaration rather than a silent skip: {phrase}")

    def test_the_archive_is_verified_against_the_commit_ci_checked_out(self) -> None:
        block = self.step_block("Verify the archived native evidence")
        self.assertIn("write_artifact_receipt.py", block)
        self.assertIn("--verify-against", block)
        self.assertIn("${{ github.sha }}", block)

    def test_the_pressed_state_gate_is_executed_and_required(self) -> None:
        """CL-16 step 1 has no check unless a job runs it, and a forgiven one would guard nothing."""
        block = self.step_block("Pressed-state motion gate")
        self.assertIn("scripts/audit/pressed_state_motion_via_cdp.py", block)
        self.assertIn("--json-out .project-local/runs/ci/pressed_motion_gate.json", block)
        self.assertNotIn("continue-on-error", block,
                         "a pressed gate that is forgiven is a claim that the tokens are wired, not a check")

    def test_the_built_native_binary_is_reachable_off_the_runner(self) -> None:
        """A binary that never leaves CI cannot be looked at, so 'the desktop entry' is only ever a claim.

        The local chain cannot produce one at all (no MSVC linker, and `windres` is handed this repository's
        space-containing path unquoted), which is why the job builds it. Uploading it is what makes the
        native shell inspectable without anybody installing a toolchain; a missing file must be a red step.
        """
        block = self.step_block("Upload the native release binary")
        # Pinned, and asserted as pinned. The first version of this check looked for
        # `actions/upload-artifact@v4` and passed -- on the exact bytes that `verify_supply_chain.py` and
        # actionlint both convict (`SUPPLY_CHAIN_FAIL …:390: action must use a full commit SHA`). A wiring
        # test that repeats a mutable tag cannot fail for the reason the repository cares about.
        self.assertIn("actions/upload-artifact@ea165f8d65b6e75b540449e92b4886f43607fa02 # v4.4.3", block,
                      "the upload step must name the commit it runs, with its version comment")
        self.assertNotIn("actions/upload-artifact@v4", block,
                         "a tag reference is a moving target; this repository pins actions by SHA")
        self.assertIn("apps/observer/src-tauri/target/release/app.exe", block)
        self.assertIn("if-no-files-found: error", block,
                      "an upload that tolerates a missing exe reports success for a build that produced nothing")

    def test_the_native_evidence_is_in_the_upload_list(self) -> None:
        upload = self.text.split("name: ci-summary-observer", 1)[1].split("if-no-files-found", 1)[0]
        for path in (".project-local/artifacts/native-evidence/",
                     ".project-local/runs/u19_webview_readback.json",
                     ".project-local/runs/u19_native_surface_unverified.json",
                     ".project-local/runs/ci/window_state_readback.json",
                     ".project-local/runs/ci/desktop_capability.json"):
            self.assertIn(path, upload, f"{path} is still not archived")

    def test_the_capability_probe_still_writes_the_artifact_u19_consumes(self) -> None:
        """u19 reads the probe report by this default path; the two must not drift apart."""
        self.assertIn("--json-out .project-local/runs/ci/desktop_capability.json", self.text)
        self.assertEqual(Path(".project-local/runs/ci/desktop_capability.json"),
                         Path(u19.CAPABILITY_REPORT).relative_to(Path(u19.ROOT)))


if __name__ == "__main__":
    unittest.main()

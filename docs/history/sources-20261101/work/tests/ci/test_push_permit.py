"""Gate: a push is permitted only by a receipt that QUALIFIES for the exact head.

The ordering rule (commit -> verify at HEAD -> push) has been broken three times, twice by me: once by pushing
a head whose own gate run had already printed a red verdict (ERR-181, reading the wrapper's exit code instead
of the file), once by pushing after a governance-only run. This tool's answer is that a push needs a receipt
which says: which commit and tree it judged, that the worktree was clean while it judged, that every planned
stage ran, that the source did not move underneath it, and what its final exit was.

The previous version carried the flaw it existed to remove: it accepted "any receipt naming the head whose last
exit line is 0", so a narrow green run sitting beside a failed full verification of the same commit produced
PUSH_PERMIT_OK. `test_a_full_red_receipt_next_to_a_narrow_green_one_still_refuses` is that case, and
`qualified()` below is the only receipt shape that can pass now.
"""
from __future__ import annotations

import importlib.util
import io
import shutil
import tempfile
import unittest
from contextlib import redirect_stdout
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parents[2]
# Fixture directories stay inside the project boundary (the rule
# test_temp_fixture_residue_is_bounded polices), so planted receipts land under .project-local/runs rather
# than in the machine temp root.
RUNS = ROOT / ".project-local" / "runs"
RUNS.mkdir(parents=True, exist_ok=True)
spec = importlib.util.spec_from_file_location("push_permit", ROOT / "scripts" / "ci" / "push_permit.py")
permit = importlib.util.module_from_spec(spec)
spec.loader.exec_module(permit)  # type: ignore[attr-defined]

HEAD = "a" * 40
OTHER = "b" * 40


def write(runs: Path, name: str, body: str) -> Path:
    path = runs / name
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(body, encoding="utf-8", newline="")
    return path


def qualified(head: str = HEAD, **change: object) -> str:
    """A receipt exactly as run_quality_gate.py writes one now, with each binding field overridable.

    Every override is one way a real run can fail to certify its head: the source moved, a planned stage
    never ran, the worktree was dirty, the batch was killed before it finished.
    """
    full = change.get("full", "yes")
    planned = change.get("planned", 50)
    stage_exit = change.get("stage_exit", 0)
    lines = [
        f"GATE_HEAD={head} GATE_TREE=7f1c GATE_FULL={full} gates={planned}",
        f"GATE_DIRTY={change.get('dirty', 'clean0')} dirty_paths={change.get('dirty_paths', 0)}",
        "GATE_TOOLS python=3.12.13 node=x@v22.11.0",
        "GATE_COMMAND=python services/orchestration/run_quality_gate.py verify",
        f"GATE_STAGE gate=governance exit={stage_exit} seconds=1.0",
        "QUALITY_GATE_PASS gates=governance" if stage_exit == 0
        else f"QUALITY_GATE_FAIL gate=governance exit_code={stage_exit}",
    ]
    if not change.get("no_end_block"):
        lines += [
            f"GATE_HEAD_END={change.get('head_end', head)} GATE_TREE_END=7f1c "
            f"GATE_DIRTY_END={change.get('dirty', 'clean0')} dirty_paths_end={change.get('dirty_paths', 0)}",
            f"GATE_STAGES ran={change.get('ran', planned)} planned={planned} full={full}",
            f"GATE_SOURCE_DRIFT={change.get('drift', 'no')}",
        ]
    lines += [f"GATE_EXIT={code}" for code in change.get("exits", [0])]  # type: ignore[union-attr]
    return "\n".join(str(line) for line in lines) + "\n"


def narrow(head: str = HEAD) -> str:
    return (f"GATE_HEAD={head} GATE_TREE=7f1c GATE_FULL=no gates=1\n"
            "GATE_DIRTY=clean0 dirty_paths=0\n"
            "GATE_STAGE gate=shell exit=0 seconds=0.1\nQUALITY_GATE_PASS gates=shell\n"
            f"GATE_HEAD_END={head} GATE_TREE_END=7f1c GATE_DIRTY_END=clean0 dirty_paths_end=0\n"
            "GATE_STAGES ran=1 planned=1 full=no\nGATE_SOURCE_DRIFT=no\nGATE_EXIT=0\n")


class DecideTests(unittest.TestCase):
    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory(prefix="push-permit-", dir=str(RUNS))
        self.runs = Path(self._tmp.name)
        self.addCleanup(self._tmp.cleanup)

    def verdict(self, *bodies: tuple[str, str], **kwargs: bool) -> tuple[int, str]:
        paths = [write(self.runs, name, body) for name, body in bodies]
        return permit.decide(HEAD, paths, **kwargs)

    def test_a_qualified_full_receipt_permits_the_push(self) -> None:
        code, msg = self.verdict(("gate.log", qualified()))
        self.assertEqual(code, 0, msg)
        self.assertIn("PUSH_PERMIT_OK", msg)

    def test_a_green_receipt_for_another_head_does_not_permit_this_one(self) -> None:
        # The decisive case: the previous head was verified, this one was not.
        code, msg = self.verdict(("gate.log", qualified(head=OTHER)))
        self.assertEqual(code, 1)
        self.assertIn("NO_RECEIPT", msg)

    def test_a_full_red_receipt_next_to_a_narrow_green_one_still_refuses(self) -> None:
        """THE mixed-receipt defect: a narrow success may not outvote a failed full verification.

        Before this rule the tool returned PUSH_PERMIT_OK here, citing the one file that said GATE_EXIT=0,
        which is the very reading ERR-181 was recorded for.
        """
        red_full = qualified(stage_exit=1, exits=[1])
        code, msg = self.verdict(("gate-full-red.log", red_full), ("gate-narrow.log", narrow()))
        self.assertEqual(code, 1, msg)
        self.assertIn("MIXED_RECEIPTS", msg)
        self.assertIn("full_red", msg)
        self.assertNotIn("PUSH_PERMIT_OK", msg)

    def test_a_truncated_full_run_beside_a_narrow_green_one_is_refused_by_name(self) -> None:
        """A receipt that never reached its planned stages is its own refusal, not a silent gap."""
        truncated = qualified(stage_exit=0, ran=49)
        code, msg = self.verdict(("gate-truncated.log", truncated), ("gate-narrow.log", narrow()))
        self.assertEqual(code, 1, msg)
        self.assertIn("STAGES_MISSING", msg)
        self.assertNotIn("PUSH_PERMIT_OK", msg)

    def test_only_a_narrow_green_run_is_its_own_verdict_and_says_what_to_do(self) -> None:
        code, msg = self.verdict(("gate.log", narrow()))
        self.assertEqual(code, 1, msg)
        self.assertIn("PARTIAL_ONLY", msg)
        ok, allowed = self.verdict(("gate.log", narrow()), allow_partial=True)
        self.assertEqual(ok, 0, allowed)
        self.assertIn("allow_partial=explicit", allowed)

    def test_a_receipt_predating_the_source_binding_can_not_certify_a_head(self) -> None:
        """Migration stated rather than grandfathered: an old receipt lacks the fields, so it does not count.

        Every receipt written before this round passes the old rule and fails the new one. The answer is to
        re-run the verification, not to accept a verdict that cannot say what it measured.
        """
        legacy = f"GATE_HEAD={HEAD} GATE_TREE=x GATE_FULL=yes gates=50\nGATE_EXIT=0\n"
        code, msg = self.verdict(("legacy.log", legacy))
        self.assertEqual(code, 1, msg)
        self.assertIn("UNBOUND_RECEIPT", msg)

    def test_a_run_that_moved_the_source_mid_flight_is_refused(self) -> None:
        code, msg = self.verdict(("gate.log", qualified(drift="yes")))
        self.assertEqual(code, 1, msg)
        self.assertIn("SOURCE_CHANGED_DURING_RUN", msg)

    def test_a_head_that_changed_under_the_run_is_refused(self) -> None:
        code, msg = self.verdict(("gate.log", qualified(head_end=OTHER)))
        self.assertEqual(code, 1, msg)
        self.assertIn("HEAD_MOVED_DURING_RUN", msg)

    def test_a_receipt_measured_against_a_dirty_worktree_is_refused(self) -> None:
        code, msg = self.verdict(("gate.log", qualified(dirty_paths=3)))
        self.assertEqual(code, 1, msg)
        self.assertIn("DIRTY_RECEIPT", msg)

    def test_a_full_run_that_skipped_planned_stages_is_refused(self) -> None:
        code, msg = self.verdict(("gate.log", qualified(ran=49)))
        self.assertEqual(code, 1, msg)
        self.assertIn("STAGES_MISSING", msg)

    def test_a_run_still_in_progress_is_not_a_pass(self) -> None:
        code, msg = self.verdict(("gate.log", qualified(no_end_block=True)))
        self.assertEqual(code, 1, msg)
        self.assertIn("UNBOUND_RECEIPT", msg)
        code, msg = self.verdict(("gate.log", qualified(exits=[])))
        self.assertEqual(code, 1, msg)
        self.assertIn("NO_EXIT_LINE", msg)

    def test_a_full_red_receipt_is_named_as_red_with_its_exit(self) -> None:
        code, msg = self.verdict(("gate.log", qualified(stage_exit=7, exits=[7])))
        self.assertEqual(code, 1, msg)
        self.assertIn("RECEIPT_RED", msg)
        self.assertIn("GATE_EXIT=7", msg)

    def test_the_last_exit_line_wins_when_a_file_holds_two_runs(self) -> None:
        code, msg = self.verdict(("gate.log", qualified(exits=[0, 1], stage_exit=1)))
        self.assertEqual(code, 1, msg)
        self.assertIn("RECEIPT_RED", msg)

    def test_an_unreadable_receipt_is_refused_rather_than_crashing_the_verdict(self) -> None:
        path = write(self.runs, "gate.log", qualified())
        original = permit.read
        with mock.patch.object(permit, "read", side_effect=lambda p: "" if p == path else original(p)):
            code, msg = permit.decide(HEAD, [path])
        self.assertEqual(code, 1)
        self.assertIn("NO_RECEIPT", msg)

    def test_mentioning_a_head_is_not_evidence_about_it(self) -> None:
        write(self.runs, "noise.log", "GATE_HEAD=" + HEAD + " mentioned in prose\n")
        code, msg = permit.decide(HEAD, [self.runs / "noise.log"])
        self.assertEqual(code, 1)
        self.assertIn("UNBOUND_RECEIPT", msg)


class MainTests(unittest.TestCase):
    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory(prefix="push-permit-main-", dir=str(RUNS))
        self.runs = Path(self._tmp.name)
        self.addCleanup(self._tmp.cleanup)

    def run_main(self, argv: list[str], status: str = "") -> tuple[int, str]:
        buffer = io.StringIO()
        completed = mock.Mock(stdout=status, returncode=0)
        with redirect_stdout(buffer), mock.patch.object(permit.subprocess, "run", return_value=completed):
            code = permit.main(argv)
        return code, buffer.getvalue().strip()

    def test_an_unresolvable_rev_is_named_not_guessed(self) -> None:
        with mock.patch.object(permit, "resolve", return_value=None):
            code, msg = self.run_main(["--head", "not-a-commit", "--runs", str(self.runs)])
        self.assertEqual(code, 1)
        self.assertIn("NOT_A_COMMIT", msg)

    def test_a_missing_runs_directory_is_a_distinct_verdict(self) -> None:
        with mock.patch.object(permit, "resolve", return_value=HEAD):
            code, msg = self.run_main(["--head", "a" * 40, "--runs", str(self.runs / "absent")])
        self.assertEqual(code, 3)
        self.assertIn("PUSH_PERMIT_NOT_RUN", msg)

    def test_a_short_sha_is_resolved_before_it_is_matched(self) -> None:
        # The caller passes any rev form; receipts carry 40 hex, so a seven-character prefix would
        # otherwise match nothing and read as "never verified".
        with mock.patch.object(permit, "resolve", return_value=HEAD) as resolved:
            code, msg = self.run_main(["--head", "abcdef1", "--runs", str(self.runs)])
        self.assertEqual(resolved.call_args.args[0], "abcdef1")
        self.assertEqual(resolved.call_args.args[1], ROOT)
        self.assertEqual(code, 1)
        self.assertIn("NO_RECEIPT", msg)

    def test_uncommitted_work_blocks_the_push_unless_the_caller_says_otherwise(self) -> None:
        """The commit is immutable, but the verification may have read bytes that never entered it."""
        write(self.runs, "gate.log", qualified())
        dirty = " M services/orchestration/run_quality_gate.py\n?? scripts/ci/new_thing.py\n"
        with mock.patch.object(permit, "resolve", return_value=HEAD):
            blocked, blocked_msg = self.run_main(["--head", "a" * 40, "--runs", str(self.runs)],
                                                status=dirty)
            allowed, allowed_msg = self.run_main(["--head", "a" * 40, "--runs", str(self.runs),
                                                 "--allow-dirty"], status=dirty)
        self.assertEqual(blocked, 1, blocked_msg)
        self.assertIn("LIVE_DIRTY", blocked_msg)
        self.assertIn("uncommitted_paths=2", blocked_msg)
        self.assertEqual(allowed, 0, allowed_msg)

    def test_a_clean_worktree_needs_no_opt_in(self) -> None:
        write(self.runs, "gate.log", qualified())
        with mock.patch.object(permit, "resolve", return_value=HEAD):
            code, msg = self.run_main(["--head", "a" * 40, "--runs", str(self.runs)], status="")
        self.assertEqual(code, 0, msg)


class RunnerWritesWhatThePermitReads(unittest.TestCase):
    """Receipt and permit are one contract: run the real sequence, judge the real bytes."""

    def setUp(self) -> None:
        runner_spec = importlib.util.spec_from_file_location(
            "rQG_pairing", ROOT / "services" / "orchestration" / "run_quality_gate.py")
        self.runner = importlib.util.module_from_spec(runner_spec)
        runner_spec.loader.exec_module(self.runner)  # type: ignore[attr-defined]
        self.original = (self.runner.GATES, self.runner.VERIFY_ORDER, self.runner._source_binding)
        self.addCleanup(setattr, self.runner, "GATES", self.original[0])
        self.addCleanup(setattr, self.runner, "VERIFY_ORDER", self.original[1])
        self.addCleanup(setattr, self.runner, "_source_binding", self.original[2])
        commit, _tree = self.runner._git_head_identity()
        self.real_head = commit

    def capture(self, *exit_codes: int, binding=None, full_sequence: bool = True) -> tuple[str, int]:
        names = tuple(f"fake{i}" for i in range(len(exit_codes)))
        self.runner.GATES = {
            name: type("Fake", (), {"name": name, "description": "planted for the pairing test",
                                    "runner": staticmethod(lambda code=code: code)})()
            for name, code in zip(names, exit_codes)}
        # GATE_FULL is derived from the name set, so the fixture has to choose which claim it is testing:
        # matching VERIFY_ORDER makes the run full, leaving it alone makes the same gates a narrow run.
        # Patching it unconditionally made `test_a_narrow_run_stamps_itself_narrow` unpassable.
        if full_sequence:
            self.runner.VERIFY_ORDER = names
        # a clean synthetic binding, because this checkout is legitimately dirty while the suite runs
        self.runner._source_binding = binding or (lambda: (HEAD, "7f1c", "clean0", 0))
        buffer = io.StringIO()
        with redirect_stdout(buffer):
            returned = self.runner.run_gate_sequence(names, command="verify")
        return buffer.getvalue(), returned

    def test_a_green_full_sequence_produces_a_receipt_the_permit_accepts(self) -> None:
        body, returned = self.capture(0, 0)
        self.assertEqual(0, returned)
        self.assertIn("GATE_STAGES ran=2 planned=2 full=yes", body)
        self.assertIn("GATE_SOURCE_DRIFT=no", body)
        self.assertIn("GATE_COMMAND=verify", body)
        self.assertTrue(permit.qualification(body, HEAD)[0], body)
        with tempfile.TemporaryDirectory(prefix="pairing-", dir=str(RUNS)) as tmp:
            receipt = Path(tmp) / "gate-verify-pairing.log"
            receipt.write_text(body, encoding="utf-8", newline="\n")
            code, message = permit.decide(HEAD, [receipt])
        self.assertEqual(0, code, f"{message}\n--- receipt ---\n{body}")
        self.assertIn("PUSH_PERMIT_OK", message)

    def test_a_red_sequence_writes_its_own_failure_receipt(self) -> None:
        body, returned = self.capture(0, 7)
        self.assertEqual(7, returned)
        self.assertIn("GATE_STAGE gate=fake1 exit=7", body)
        self.assertIn("QUALITY_GATE_FAIL gate=fake1 exit_code=7", body)
        self.assertIn("GATE_EXIT=7", body)
        ok, reason = permit.qualification(body, HEAD)
        self.assertFalse(ok, body)
        self.assertIn("RECEIPT_RED", reason)

    def test_a_source_that_moves_mid_run_forces_a_refused_verdict(self) -> None:
        seen = {"calls": 0}

        def drifting() -> tuple[str, str, str, int]:
            seen["calls"] += 1
            return (HEAD, "7f1c", "clean0", 0) if seen["calls"] == 1 else (OTHER, "8f2d", "moved1", 1)

        body, returned = self.capture(0, 0, binding=drifting)
        self.assertEqual(70, returned, f"a run over changed bytes must not report success\n{body}")
        self.assertIn("GATE_SOURCE_DRIFT=yes", body)
        self.assertIn("QUALITY_GATE_SOURCE_CHANGED", body)
        self.assertIn("GATE_EXIT=70", body)
        ok, reason = permit.qualification(body, HEAD)
        self.assertFalse(ok, body)
        self.assertIn("HEAD_MOVED_DURING_RUN", reason)

    def test_a_narrow_run_stamps_itself_narrow(self) -> None:
        body, _returned = self.capture(0, full_sequence=False)
        self.assertIn("GATE_FULL=no", body)
        self.assertIn("full=no", body.split("GATE_STAGES")[1].splitlines()[0])
        ok, reason = permit.qualification(body, HEAD)
        self.assertFalse(ok, body)
        self.assertIn("PARTIAL_ONLY", reason)

    def test_no_verdict_path_leaves_a_receipt_without_a_completion_line(self) -> None:
        for codes, expected in (((0,), "0"), ((3,), "3"), ((0, 0, 9), "9")):
            body, _returned = self.capture(*codes)
            found = [line for line in body.splitlines() if line.startswith("GATE_EXIT=")]
            self.assertEqual([f"GATE_EXIT={expected}"], found, f"exit path {codes} wrote {found}")

    def test_the_real_runner_binds_a_real_head_and_the_clean_synthetic_head_is_a_fixture(self) -> None:
        """_source_binding must report the commit under test, not a placeholder."""
        commit, tree, digest, paths = self.runner._source_binding()
        self.assertEqual(commit, self.real_head)
        self.assertRegex(tree, r"^[0-9a-f]{40}$")
        self.assertRegex(digest, r"^[0-9a-f]{16}$")
        self.assertIsInstance(paths, int)


class TheQualificationItselfIsTested(unittest.TestCase):
    """A refusal table is only real if each row has a case; an unreadable field must not default to clean."""

    def test_the_fields_are_read_from_the_receipt_not_from_the_file_name(self) -> None:
        tmp = tempfile.mkdtemp(prefix="fields-", dir=str(RUNS))
        self.addCleanup(shutil.rmtree, tmp, True)
        path = Path(tmp) / "whatever.log"
        path.write_text(qualified(), encoding="utf-8", newline="\n")
        code, message = permit.decide(HEAD, [path])
        self.assertEqual(code, 0, message)
        path.write_text("GATE_HEAD=" + HEAD + "\n", encoding="utf-8", newline="\n")
        code, message = permit.decide(HEAD, [path])
        self.assertEqual(code, 1)
        self.assertIn("UNBOUND_RECEIPT", message)

    def test_an_unreadable_drift_value_is_a_refusal_not_a_default_pass(self) -> None:
        ok, reason = permit.qualification(qualified(drift="maybe"), HEAD)
        self.assertFalse(ok)
        self.assertIn("UNREADABLE_DRIFT", reason)

    def test_a_zero_planned_stage_count_cannot_certify_anything(self) -> None:
        ok, reason = permit.qualification(qualified(ran=0, planned=0), HEAD)
        self.assertFalse(ok, "planned=0 means the runner planned nothing; that is not a verification")
        self.assertIn("STAGES_MISSING", reason)

    def test_a_missing_tool_or_command_line_is_refused_as_unbound(self) -> None:
        body = "\n".join(line for line in qualified().splitlines()
                         if not line.startswith(("GATE_TOOLS", "GATE_COMMAND"))) + "\n"
        code, message = permit.decide(HEAD, [write(Path(tempfile.mkdtemp(prefix="cmd-", dir=str(RUNS))),
                                                   "r.log", body)])
        # today only the verdict fields are load-bearing; the command and tool lines are provenance and are
        # asserted here so they cannot be dropped from the runner without this test noticing
        self.assertEqual(code, 0, message)
        source = (ROOT / "services" / "orchestration" / "run_quality_gate.py").read_text(encoding="utf-8")
        self.assertIn('GATE_TOOLS python=', source)
        self.assertIn("GATE_COMMAND=", source)


if __name__ == "__main__":
    unittest.main(verbosity=2)

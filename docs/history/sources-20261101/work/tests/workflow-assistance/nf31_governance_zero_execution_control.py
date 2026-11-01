"""NF31 · every member the governance batch discovers must account for tests it executed.

Why this exists (measured 2026-10-26 on this tree, before the fix):
`mandatory_discovery_modules()` decided a member's runner by asking whether the literal text `unittest`
appeared anywhere in the file. Ten members were executed by a runner that collects nothing from them --
nine genuine pytest modules went to `python <file>` (imported, printed nothing, exit 0) and one pytest
module that only MENTIONS `unittest` in a comment went to `python -m unittest` (printed `Ran 0 tests /
OK`, exit 0). 78 test cases had never been executed by anything, and the batch still printed PASS,
because the batch's only evidence was one shared `Ran N` banner plus a returncode.

A returncode says a process did not crash. It is not evidence that a test ran, and this module is the
control that keeps that distinction from collapsing again: each check here writes a real member into a
scratch directory, runs it through the REAL batch runner, and demands a named verdict.

This module is pytest-style on purpose (`nf*.py` is auto-discovered by the mandatory glob, and the AST
classifier routes it to `python -m pytest`), so it is itself proof that the new route executes what it
claims to.
"""
from __future__ import annotations

import importlib.util
import os
import shutil
import uuid
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
SPEC = importlib.util.spec_from_file_location(
    "run_quality_gate_under_nf31", ROOT / "services" / "orchestration" / "run_quality_gate.py"
)
assert SPEC and SPEC.loader
GATE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(GATE)

# Set in the environment of the LIVE-TREE check's nested batch. Without it the nested batch runs this
# module again, which runs the batch again, without end; the inner instance skips only this one test and
# still executes every other check here, so it never becomes a ZERO_EXECUTED member itself.
NEST_MARKER = "WL_NF31_LIVE_BATCH"


@pytest.fixture
def scratch_dir() -> Path:
    # Project data boundary: a control module is a runtime artifact, so it lands under the project's own
    # runtime root and never inside a tracked directory (the mandatory glob would then adopt it).
    path = ROOT / ".project-local" / "runs" / "tmp" / f"nf31-{os.getpid()}-{uuid.uuid4().hex[:8]}"
    path.mkdir(parents=True, exist_ok=True)
    try:
        yield path
    finally:
        shutil.rmtree(path, ignore_errors=True)


def member_id(path: Path) -> str:
    """Absolute path as a member id: `governance_member_path` keeps absolutes, so a control can be run by
    the real batch runner without ever being written into the tracked tree."""
    return path.as_posix()


def write(path: Path, text: str) -> Path:
    path.write_text(text, encoding="utf-8")
    return path


def test_kind_comes_from_the_tree_and_not_from_a_substring(scratch_dir: Path) -> None:
    # The exact shape that was mis-routed: a pytest module whose only `unittest` is prose in a comment.
    mention = write(scratch_dir / "probe_mention.py",
                    '# this module is pytest-style; the word unittest appears only here\n\n\n'
                    'def test_a_case():\n    assert True\n')
    assert GATE.governance_member_kind(mention) == "pytest"

    case = write(scratch_dir / "probe_case.py",
                 'import unittest\n\n\n'
                 'class ProbeCase(unittest.TestCase):\n'
                 '    def test_a_case(self):\n        self.assertTrue(True)\n\n'
                 'if __name__ == "__main__":\n    unittest.main()\n')
    assert GATE.governance_member_kind(case) == "unittest"

    # A TestCase reached only through a local mixin is still a TestCase; judging the literal base name
    # would call nf08-style modules pytest and silently drop every method they inherit.
    mixin = write(scratch_dir / "probe_mixin.py",
                  'import unittest\n\n\n'
                  'class _Guard(unittest.TestCase):\n    pass\n\n\n'
                  'class TestThroughTheGuard(_Guard):\n'
                  '    def test_a_case(self):\n        self.assertTrue(True)\n')
    assert GATE.governance_member_kind(mixin) == "unittest"

    # Neither shape is a test module: it is a self-executing check script and must prove it ran by printing.
    hollow = write(scratch_dir / "probe_hollow.py", "VALUE = 1\n")
    assert GATE.governance_member_kind(hollow) == "script"

    # Unparseable is not "carries no tests": it goes to the route whose child fails loudly.
    broken = write(scratch_dir / "probe_broken.py", "def test_a_case(:\n    assert True\n")
    assert GATE.governance_member_kind(broken) == "script"


def test_a_hollow_member_exits_zero_and_is_still_a_named_failure(scratch_dir: Path) -> None:
    """The hole, isolated: rc == 0 AND zero cases executed. Returncode cannot be the verdict."""
    hollow = member_id(write(scratch_dir / "probe_hollow.py",
                             '# mentions unittest but owns no test at all\nVALUE = 1\n'))
    exit_code, _output, outcomes = GATE._run_governance_batch([hollow])
    assert exit_code == 0, "the control is only useful if a silent module exits 0 exactly like a passing one"
    assert outcomes[hollow].executed == 0
    assert GATE.governance_hollow_members([hollow], outcomes) == [f"ZERO_EXECUTED {hollow}"]


def test_a_pytest_member_is_executed_and_counted(scratch_dir: Path) -> None:
    member = member_id(write(scratch_dir / "probe_pytest.py",
                             '# the old classifier sent this to -m unittest, which collected 0 of 2\n\n\n'
                             'def test_first_case():\n    assert True\n\n\n'
                             'def test_second_case():\n    assert True\n'))
    exit_code, _output, outcomes = GATE._run_governance_batch([member])
    assert exit_code == 0
    outcome = outcomes[member]
    assert (outcome.kind, outcome.collected, outcome.executed) == ("pytest", 2, 2), outcome
    assert GATE.governance_hollow_members([member], outcomes) == []


def test_batch_verdict_names_every_hollow_member(scratch_dir: Path) -> None:
    """Mixed batch: a real pytest member, a silent member, and a member that cannot even be collected."""
    healthy = member_id(write(scratch_dir / "probe_healthy.py", "def test_case():\n    assert True\n"))
    hollow_script = member_id(write(scratch_dir / "probe_hollow.py", "VALUE = 1\n"))
    # pytest-shaped, but the module explodes on import, so nothing is collected and nothing runs. This is
    # the shape the shared banner made invisible: the batch still printed a big `Ran N` for everybody else.
    uncollectable = member_id(write(
        scratch_dir / "probe_uncollectable.py",
        '# mentions unittest, owns a real test\n\n\ndef test_case():\n    assert True\n\n\n'
        'raise RuntimeError("import-time explosion planted by nf31")\n',
    ))
    members = [healthy, hollow_script, uncollectable]
    exit_code, _output, outcomes = GATE._run_governance_batch(members)
    named = GATE.governance_hollow_members(members, outcomes)
    assert outcomes[healthy].executed == 1
    assert named == [f"ZERO_EXECUTED {hollow_script}", f"ZERO_EXECUTED {uncollectable}"], named
    # Returncode is not the evidence and must not become the mechanism: the silent member is the one that
    # exits 0, and the accounting is what convicts it.
    assert outcomes[hollow_script].exit_code == 0
    assert outcomes[uncollectable].collected == 0
    assert exit_code != 0, "the uncollectable member fails the batch on its own terms too"

    # And a batch whose ONLY hollow member is the silent one still has to be refused by the gate itself.
    silent_only = [healthy, hollow_script]
    silent_exit, _silent_output, silent_outcomes = GATE._run_governance_batch(silent_only)
    assert silent_exit == 0, "silence exits 0; only the accounting can see it"
    assert GATE.governance_hollow_members(silent_only, silent_outcomes) == [f"ZERO_EXECUTED {hollow_script}"]


def test_gate_governance_fails_closed_naming_the_silent_member(
    scratch_dir: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    """End to end on the gate function: exit 0 from the child, ZERO_EXECUTED from the gate."""
    member = member_id(write(scratch_dir / "probe_hollow.py", "VALUE = 1\n"))
    monkeypatch.setattr(GATE, "mandatory_discovery_modules", lambda: [member])
    assert GATE.gate_governance() == 1
    printed = capsys.readouterr().out
    assert "QUALITY_GATE_GOVERNANCE_FAIL" in printed
    assert f"ZERO_EXECUTED {member}" in printed


def test_gate_governance_reports_the_newly_executed_pytest_cases(
    scratch_dir: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    """The PASS line counts what only the pytest route can count."""
    member = member_id(write(scratch_dir / "probe_pytest.py",
                             'def test_one():\n    assert True\n\n\n'
                             'def test_two():\n    assert True\n\n\n'
                             'def test_three():\n    assert True\n'))
    monkeypatch.setattr(GATE, "mandatory_discovery_modules", lambda: [member])
    assert GATE.gate_governance() == 0, capsys.readouterr().out
    printed = capsys.readouterr().out
    assert "QUALITY_GATE_GOVERNANCE_PASS modules=1 executed=3 ran=3 skipped=0" in printed


def test_accounting_rows_are_derived_not_assumed(scratch_dir: Path) -> None:
    """A member missing from the accounting is hollow, never a pass by omission."""
    member = member_id(write(scratch_dir / "probe_hollow.py", "VALUE = 1\n"))
    assert GATE.governance_hollow_members([member], {}) == [f"ZERO_EXECUTED {member}"]


def test_live_tree_leaves_no_member_that_executes_nothing(monkeypatch: pytest.MonkeyPatch) -> None:
    """The check that cannot pass vacuously: the REAL discovered list, the REAL runner.

    Before the fix this assertion was red with exactly the ten silently-green members named. It costs one
    extra batch run, and it is the only form that proves the classifier matches how this repository has
    actually written its tests rather than how a substring heuristic guessed.
    """
    if os.environ.get(NEST_MARKER):
        pytest.skip("already inside the live batch; the outer instance holds this verdict")
    members = GATE.mandatory_discovery_modules()
    assert members, "an empty mandatory set makes this control vacuous"
    monkeypatch.setenv(NEST_MARKER, "1")
    _exit_code, _output, outcomes = GATE._run_governance_batch(members)
    hollow = GATE.governance_hollow_members(members, outcomes)
    assert set(outcomes) == set(members), (
        f"discovered {len(members)} members, accounted for {len(outcomes)}: "
        f"{sorted(set(members) - set(outcomes))[:10]}"
    )
    assert hollow == [], (
        f"{len(hollow)} members executed zero tests, which is not coverage: {hollow[:25]}"
    )
    # Every route that can carry cases must carry at least one, or the routing table is decoration.
    for kind in ("unittest", "pytest"):
        rows = [outcome for outcome in outcomes.values() if outcome.kind == kind]
        if rows:
            assert sum(row.executed for row in rows) > 0, f"route {kind} executed nothing"

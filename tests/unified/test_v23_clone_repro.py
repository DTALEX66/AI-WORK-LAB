# SPDX-License-Identifier: MIT
"""V23: what a fresh clone can actually run.

The audit entry invites an independent reviewer to clone the repo and re-run the
commands, so "rerunnable" has to mean something about a clone, not about this working
copy. Two things were found by checking that claim rather than assuming it:

* several legacy tests pass ``.project-local/task-runtime`` to ``mkdtemp`` as its parent,
  and that directory is gitignored — a clone had no parent to create a temp dir in, so
  collection-time setup raised before any assertion ran (now created by an autouse
  fixture in ``tests/conftest.py``);
* tests that shell out to ``.venv\\Scripts\\python.exe`` or read the two read-only source
  repositories are legitimately machine-bound, since neither is in Git. Those are
  excluded here by scanning each file, and the exclusion list is printed rather than
  asserted away, so nobody can quietly shrink what "the suite passes" covers.

The scan reads test files only, which is itself a dependency it cannot see, so two guards
close that gap: the shared fixture's project root must stay inside the checkout
(``test_the_shared_fixture_project_root_stays_inside_the_checkout``), and the source-root
spelling the scan misses must stay proven tolerant of the sources being absent by measurement
rather than by exclusion (``test_the_unscanned_parent_source_spelling_is_measured_not_
reclassified``). Both are about the 2026-11-01 control/treatment run recorded in
``.project-local/runs/independence-20261101.json``; the 15-node delta is frozen in this file
because a clone cannot read that gitignored measurement.
"""
from __future__ import annotations

import atexit
import os
import re
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

TARGET_ROOT = Path(__file__).resolve().parents[2]
#: ``.venv``, the two read-only source repositories, the live dev workspace and the
#: isolated-install receipts under ``.project-local/build`` are all prerequisites of this
#: machine or this checkout: none of them is in Git. A test that reads one is honestly
#: machine-bound, and saying so here keeps "the clone runs the suite" from silently
#: meaning "whichever subset happens not to need anything".
PREREQ = re.compile(r"\.venv|All projects[\\/](WORK-LAB|DESIGN-LAB)|"
                    r"WORK_SOURCE_ROOT|DESIGN_SOURCE_ROOT|LIVE_STORES|"
                    r"[.]git[\"'\s\\/]+hooks|"
                    r"[.]project-local[\"'\s\\/]+build")

#: A second spelling of "the read-only source repository next door" that ``PREREQ`` cannot
#: see, because it is relative to the checkout instead of naming the machine.
PARENT_SOURCE = re.compile(r"TARGET_ROOT\.parent\s*/\s*[\"'](WORK-LAB|DESIGN-LAB)[\"']")
#: ``tests/conftest.py`` assigns the project root every ``work_project`` test is bound to.
FIXED_ROOT_ASSIGNMENT = re.compile(r"^LIVE_WORK_ROOT\s*=\s*(.+)$", re.M)

#: The 15 nodes that failed when, and only when, the two source roots were redirected to
#: paths that do not exist. Frozen here because the measurement itself lives in
#: ``.project-local/`` (gitignored, so a clone cannot read it):
#: ``.project-local/runs/independence-20261101.json``, head ``2477d7b``,
#: control 63 problem nodes / treatment 78, delta exactly these 15, none running the other
#: way. Twelve of them came from ``tests/conftest.py`` binding ``work_project`` to the
#: host's WORK-LAB; the remaining ones are the audit-state generator and its census node.
MEASURED_SOURCE_ABSENCE_FAILURES = (
    "test_adapter_dispatch_is_not_allowed_this_batch",
    "test_backend_boots_twice_and_recovers_the_orphan",
    "test_concurrent_attempt_update_refuses_the_loser",
    "test_design_task_definition_pointers_match_their_bytes",
    "test_duplicate_result_refused_on_second_attempt",
    "test_entry_work_execution_detail_attempt_is_the_stored_row",
    "test_external_receipt_claim_is_not_declarable",
    "test_f07_origin_chain_is_inherited_and_cannot_be_promoted",
    "test_f07_work_project_on_real_root_stays_what_it_claims",
    "test_f09_observer_reads_answer_and_control_gate_is_enforced",
    "test_import_before_declared_handoff_refused",
    "test_stale_result_refused",
    "test_the_audit_state_check_fails_on_a_stale_census",
    "test_work_maintenance_loop_completes_and_survives_restart",
    "test_wrong_pack_and_wrong_project_results_refused",
)
#: Files that carry the unscanned parent spelling. The measurement says none of the nodes
#: defined in them appears in the list above, i.e. they tolerate the sources being gone.
MEASURED_TOLERANT_OF_ABSENT_SOURCES = (
    "tests/unified/test_v07_migration.py",
    "tests/unified/test_v14_registers.py",
    "tests/unified/test_v16_traceability.py",
    "tests/unified/test_v27_adapter_conformance.py",
)


def _test_files(root: Path) -> list[Path]:
    return sorted(p for pattern in ("tests/unified/test_v*.py", "tests/legacy/**/test_*.py")
                  for p in root.glob(pattern))


def _partition(root: Path) -> tuple[list[str], list[str]]:
    clone_safe: list[str] = []
    machine_bound: list[str] = []
    for path in _test_files(root):
        relative = path.relative_to(root).as_posix()
        if relative.startswith("tests/unified/test_v23"):
            continue  # this file itself clones, so it is not evidence about the clone
        text = path.read_text(encoding="utf-8", errors="replace")
        (machine_bound if PREREQ.search(text) else clone_safe).append(relative)
    return clone_safe, machine_bound


def _test_node_names(path: Path) -> list[str]:
    return re.findall(r"^def (test_\w+)", path.read_text(encoding="utf-8", errors="replace"),
                      re.M)


def _fixture_project_root(root: Path) -> Path:
    """Resolve the project root the shared ``work_project`` fixture binds tests to.

    The value is evaluated as ``tests/conftest.py`` writes it, with ``TARGET_ROOT`` set to
    the checkout being examined, so the same call answers for this working copy and for a
    clone.
    """
    text = (root / "tests" / "conftest.py").read_text(encoding="utf-8")
    assignment = FIXED_ROOT_ASSIGNMENT.search(text)
    assert assignment, "tests/conftest.py no longer names the fixture project root"
    return eval(assignment.group(1), {"__builtins__": {}},  # noqa: S307 - our own literal
                {"TARGET_ROOT": root, "Path": Path})


def _clone(suffix: str) -> Path:
    """Clone into a deliberately short root: Windows MAX_PATH already bit a rehearsal that
    ran under pytest's nested basetemp, and the migrated resource tree has long paths."""
    destination = Path(tempfile.gettempdir()) / ("awlclone-%d-%s" % (os.getpid(), suffix))
    if destination.exists():
        shutil.rmtree(destination, ignore_errors=True)
    destination.mkdir(parents=True, exist_ok=True)
    clone = destination / "c"
    completed = subprocess.run(["git", "clone", "--quiet", "--no-hardlinks",
                               str(TARGET_ROOT), str(clone)],
                              capture_output=True, text=True, encoding="utf-8",
                              errors="replace", timeout=900)
    assert completed.returncode == 0, completed.stderr[-800:]
    atexit.register(shutil.rmtree, destination, True)
    return clone


def test_a_clone_can_run_the_machine_independent_part_of_the_suite(tmp_path):
    clone = _clone("run")
    clone_local = clone / ".project-local"
    assert not clone_local.exists(), (
        "the clone already carries .project-local, so this run would not prove anything "
        "about a fresh checkout")

    clone_safe, machine_bound = _partition(clone)
    assert clone_safe, "no test was classified as clone-runnable; the scan is wrong"
    # the legacy design tests that needed the scratch parent must be inside the runnable
    # set, otherwise this test would certify a subset that never exercised the fix
    assert any("test_target_profile" in name for name in clone_safe), clone_safe

    run = subprocess.run([sys.executable, "-B", "-m", "pytest", *clone_safe, "-q",
                          "-p", "no:cacheprovider"],
                         cwd=str(clone), capture_output=True, text=True,
                         encoding="utf-8", errors="replace", timeout=3000)
    tail = run.stdout.strip().splitlines()[-1] if run.stdout.strip() else ""
    assert run.returncode == 0, (tail, run.stdout[-2000:], run.stderr[-800:])
    assert (clone_local / "task-runtime").is_dir(), (
        "the autouse fixture did not create the scratch parent in the clone")
    print("clone-runnable:", len(clone_safe), "machine-bound:", len(machine_bound))
    print(tail)


def test_the_machine_bound_set_is_named_not_assumed(tmp_path):
    """.venv and the two read-only sources are prerequisites of this machine; the split must
    stay visible, because an unlisted exclusion is how "the suite passes" comes to mean less
    than it reads."""
    clone = _clone("part")
    clone_safe, machine_bound = _partition(clone)
    assert machine_bound, "nothing was classified as machine-bound; check the scan pattern"
    assert set(machine_bound).isdisjoint(clone_safe)
    for relative in machine_bound:
        text = (clone / relative).read_text(encoding="utf-8", errors="replace")
        assert PREREQ.search(text), relative


def test_the_shared_fixture_project_root_stays_inside_the_checkout():
    """No shared fixture may bind a test to a directory outside this checkout.

    ``_partition`` can only classify what it reads: it scans each *test file*, never
    ``tests/conftest.py``. So when ``work_project`` pointed at the host's ``WORK-LAB``, twelve
    clone-runnable-looking nodes broke on a machine without that neighbour and the scan called
    them clone-safe anyway -- the classification was wrong for a dependency it could not see
    (measured: ``.project-local/runs/independence-20261101.json``, head ``2477d7b``, 63 problem
    nodes with the sources present against 78 without them). This node checks the fixture
    itself, so the blind spot has a named guard rather than a recount.
    """
    project_root = _fixture_project_root(TARGET_ROOT)
    assert project_root.is_absolute()
    assert TARGET_ROOT in project_root.parents, (
        "the shared work_project fixture binds tests to %s, which is outside the checkout "
        "%s: a clone of this repo does not carry it, and PREREQ cannot see the dependency "
        "because it only scans test files" % (project_root, TARGET_ROOT))
    assert project_root.is_dir(), "the fixture project root does not exist: %s" % project_root
    relative = project_root.relative_to(TARGET_ROOT).as_posix()
    tracked = subprocess.run(["git", "-C", str(TARGET_ROOT), "ls-files", "--", relative],
                             capture_output=True, text=True, encoding="utf-8",
                             errors="replace")
    assert tracked.returncode == 0 and tracked.stdout.strip(), (
        "the fixture project root %s exists but is not tracked, so a fresh clone gets "
        "nothing from it" % relative)


def test_the_unscanned_parent_source_spelling_is_measured_not_reclassified():
    """The spelling ``PREREQ`` cannot see must stay proven tolerant, not quietly excluded.

    ``PREREQ`` matches the absolute form (``All projects\\WORK-LAB``), not
    ``TARGET_ROOT.parent / "WORK-LAB"``. Four files use the relative form. Reclassifying them
    as machine-bound would look like a fix and would silently shrink what "a clone runs the
    suite" covers -- which defeats the point of this file, so the evidence has to be the
    measurement instead: none of the nodes defined in those files appears in
    ``MEASURED_SOURCE_ABSENCE_FAILURES``, the delta of the 2026-11-01 control/treatment run
    (``.project-local/runs/independence-20261101.json``, head ``2477d7b``, control 63 /
    treatment 78 problem nodes, 15-node delta, nothing failing the other way).
    """
    assert len(MEASURED_SOURCE_ABSENCE_FAILURES) == 15, MEASURED_SOURCE_ABSENCE_FAILURES
    assert not PREREQ.search('SOURCES = [TARGET_ROOT.parent / "WORK-LAB"]'), (
        "PREREQ now scans the parent spelling, so the exclusion below needs re-reading: the "
        "clone-safe set just changed")

    carrying = {}
    for path in _test_files(TARGET_ROOT):
        relative = path.relative_to(TARGET_ROOT).as_posix()
        if relative.startswith("tests/unified/test_v23"):
            continue
        if PARENT_SOURCE.search(path.read_text(encoding="utf-8", errors="replace")):
            carrying[relative] = _test_node_names(path)
    assert carrying, "no file carries the parent spelling any more; retire this guard's list"
    assert set(carrying) == set(MEASURED_TOLERANT_OF_ABSENT_SOURCES), (
        "the files naming a source repo as a sibling of the checkout changed: %s. The frozen "
        "measurement covered only %s, so a newly appearing file is unmeasured and a vanished "
        "one needs its guard re-derived, not copied."
        % (sorted(carrying), sorted(MEASURED_TOLERANT_OF_ABSENT_SOURCES)))

    clone_safe, machine_bound = _partition(TARGET_ROOT)
    for relative, names in carrying.items():
        failed = sorted(set(names) & set(MEASURED_SOURCE_ABSENCE_FAILURES))
        assert not failed, (
            "%s writes the source root as a sibling of the checkout, and %s of its nodes were "
            "measured failing when the sources are absent -- so this file is not tolerant, and "
            "the clone-safe classification has to change on that evidence"
            % (relative, failed))
        if relative in machine_bound:
            text = (TARGET_ROOT / relative).read_text(encoding="utf-8", errors="replace")
            without = "\n".join(line for line in text.splitlines()
                                if not PARENT_SOURCE.search(line))
            assert PREREQ.search(without), (
                "%s is machine-bound only because of its source-root spelling: the exclusion "
                "rests on the assumption this node exists to falsify" % relative)
    # and the files the measurement cleared are still counted as runnable by a clone
    still_safe = sorted(set(carrying) & set(clone_safe))
    assert still_safe, (
        "every file with the parent spelling is now excluded from the clone run: what does "
        "the clone actually cover? the measured set was %s"
        % sorted(MEASURED_TOLERANT_OF_ABSENT_SOURCES))
    print("parent-spelling files:", still_safe, "(clone-run, measured tolerant)")

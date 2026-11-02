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
(``test_the_shared_fixture_project_root_stays_inside_the_checkout``), and every root outside
this checkout must be resolved in exactly one file
(``test_the_three_outside_roots_have_exactly_one_spelling``). The second one replaces a
guard that could only rest on measurement: four test files used to spell a source root as a
sibling of the checkout, which ``PREREQ`` cannot see, so their clone-safety was argued from
the 2026-11-01 control/treatment delta recorded in
``.project-local/runs/independence-20261101.json`` (control 63 problem nodes / treatment 78)
instead of from the code. With one resolver there is nothing left to argue from.
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

#: The two spellings that used to mean "the read-only source root" outside
#: ``scripts/source_roots.py``. Either one defeats the environment switch, because a
#: generator that builds a path itself never asks the resolver what the machine said.
ABSOLUTE_SOURCE_ROOT = re.compile(r"All projects[\\/](WORK-LAB|DESIGN-LAB|Project Archiving)")
SIBLING_SOURCE_ROOT = re.compile(
    r"(?:REPO_ROOT|TARGET_ROOT|ROOT)\.parent\s*/\s*[\"'](WORK-LAB|DESIGN-LAB|Project Archiving)[\"']")
FORBIDDEN_ROOT_SPELLINGS = (ABSOLUTE_SOURCE_ROOT, SIBLING_SOURCE_ROOT)
#: The one file allowed to spell a root -- the resolver itself. Exempted by exact path, not
#: by a substring rule, so a second copy of the same spelling cannot hide behind the name.
ROOT_RESOLVER = "scripts/source_roots.py"
#: Inert material: quoted originals and history, whose bytes the registers pin by digest and
#: which this repository must not rewrite. ``docs/authority-202610`` is re-verified SHA-256 by
#: ``check_authority_index``, so editing one character there is red on its own.
INERT_PREFIXES = ("docs/history/", "docs/authority-202610/", "AI-WORK-LAB_HANDOFF",
                  "research/", ".project-local/")
#: ``tests/conftest.py`` assigns the project root every ``work_project`` test is bound to.
FIXED_ROOT_ASSIGNMENT = re.compile(r"^LIVE_WORK_ROOT\s*=\s*(.+)$", re.M)


def _active_python_files(root: Path) -> list[Path]:
    """Enumerate this checkout's own Python code: ``scripts/`` and ``tests/``, nothing inert.

    ``root`` is a parameter so a counter-example can point the enumeration at a planted file
    -- a guard whose population cannot be redirected is a guard that has never been wrong.
    """
    found = []
    for pattern in ("scripts/*.py", "tests/**/*.py"):
        for path in sorted(root.glob(pattern)):
            relative = path.relative_to(root).as_posix()
            if relative.startswith(INERT_PREFIXES):
                continue
            if relative.startswith("tests/unified/test_v23"):
                continue  # the patterns searched for are written out in this file
            if relative == ROOT_RESOLVER:
                continue  # the resolver is what owns the spelling; everything else must ask it
            found.append(path)
    return found


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


def test_the_three_outside_roots_have_exactly_one_spelling():
    """Every root outside this checkout is resolved in one file, and the guard can fail.

    The cut used to be unprovable by a single switch because the same three directories were
    spelled two ways: an absolute literal and a sibling of the checkout. The sibling form is
    invisible to ``PREREQ``, which is why the 2026-11-01 run had to *measure* a 15-node delta
    instead of excluding those files -- and why the generator that should have answered
    ``SOURCE_REPO_ABSENT`` found the real neighbour and reported register drift instead.
    ``scripts/source_roots.py`` owns both spellings now, so this names any file that still
    builds one by hand.

    Active code only: ``docs/history`` and ``research`` hold inert originals whose bytes the
    registers pin by SHA-256, the handoff package is quoted material, and this file is
    excluded because the patterns it searches for are necessarily written out in it.
    ``scripts/source_roots.py`` is exempt by exact path -- it is the file the rule is about.
    """
    offenders = {}
    for path in _active_python_files(TARGET_ROOT):
        text = path.read_text(encoding="utf-8", errors="replace")
        hits = sorted({match.group(0) for pattern in FORBIDDEN_ROOT_SPELLINGS
                       for match in pattern.finditer(text)})
        if hits:
            offenders[path.relative_to(TARGET_ROOT).as_posix()] = hits
    assert not offenders, (
        "这些文件还在自己拼来源根，所以环境变量开关到不了它们：%s" % offenders)

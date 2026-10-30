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

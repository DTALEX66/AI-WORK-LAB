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
import importlib.util
import os
import re
import shutil
import subprocess
import sys
import sysconfig
import tempfile
import time
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


#: A virtualenv's *root* is a prerequisite of this machine, but the layout under it belongs to the
#: platform that built it: Windows writes ``Scripts/python.exe``, POSIX writes ``bin/python``.
#: Eight sites spelled only the Windows form, which is what stopped 21 migration and restart nodes
#: from even starting on the audit's Linux run (N05). The ban below is on the *path construction*;
#: descriptive strings such as ``build_audit_item_closure.INTERPRETER`` ("which interpreter produced
#: that receipt") are prose about a measurement, not a locator, and are not matched.
VENV_WINDOWS_ONLY_BUILD = re.compile(
    r"[\"'][.]venv[\"']\s*/\s*[\"']Scripts[\"']\s*/\s*[\"']python\.exe")
VENV_DERIVED_BUILD = re.compile(r"[.]venv[\"']\s*/\s*\([\"']Scripts/python\.exe[\"']\s*if os\.name")


def test_the_venv_interpreter_layout_is_derived_and_agrees_with_this_interpreter():
    """Nobody may hand-build the Windows venv path, and the derived spelling is checked against
    the running interpreter's own answer for where scripts live.

    ``sysconfig.get_paths()["scripts"]`` is how the interpreter itself names that directory --
    ``Scripts`` on Windows, ``bin`` on POSIX -- so the agreement leg is a real cross-platform
    assertion rather than ``os.name`` compared with itself. What is NOT proven here is that a Linux
    host runs this suite green: this machine has no Linux interpreter to run it with, so the native
    re-run the task card asks for stays NOT_RUN and is recorded as such.
    """
    offenders = {}
    derived_sites = []
    for path in _active_python_files(TARGET_ROOT):
        text = path.read_text(encoding="utf-8", errors="replace")
        relative = path.relative_to(TARGET_ROOT).as_posix()
        hits = sorted({match.group(0) for match in VENV_WINDOWS_ONLY_BUILD.finditer(text)})
        if hits:
            offenders[relative] = hits
        if VENV_DERIVED_BUILD.search(text):
            derived_sites.append(relative)
    assert not offenders, (
        "这些文件还在按 Windows 布局自己拼 venv 解释器，POSIX 上拼出来的路径不存在：%s" % offenders)
    assert len(derived_sites) >= 7, (
        "派生布局的站点少于 7 处（7 个测试文件 + boot_probe），说明上面那条禁令可能只是没东西可管：%s"
        % derived_sites)

    layout = Path(sysconfig.get_paths()["scripts"]).name
    assert layout == ("Scripts" if os.name == "nt" else "bin"), (
        "这台机器上的解释器把自己的脚本目录叫 %r，而本仓派生布局用的是另一套名字：%s"
        % (layout, sysconfig.get_paths()["scripts"]))
    derived = TARGET_ROOT / ".venv" / (
        "Scripts/python.exe" if os.name == "nt" else "bin/python")
    assert derived.is_file(), (
        "测试与探针按平台派生出来的 venv 解释器在本机不存在：%s（这是本机的先决条件，缺它就是红，"
        "不是 skip）" % derived)


def test_falsification_a_planted_windows_only_venv_spelling_is_named(tmp_path):
    """The ban has to be able to fire: plant the old spelling where the guard's own scan looks.

    ``_active_python_files`` takes a root precisely so a counter-example can redirect the
    population; the same predicate is then applied to the derived spelling the repo uses now, which
    is what separates "this regex bans one shape" from "this regex bans everything".
    """
    scripts = tmp_path / "scripts"
    scripts.mkdir()
    old_spelling = ('TARGET_ROOT = __import__("pathlib").Path(".")\n'
                    'VENV_PYTHON = str(TARGET_ROOT / ".venv" / "Scripts" / "python.exe")\n')
    derived = ('TARGET_ROOT = __import__("pathlib").Path(".")\n'
               'VENV_PYTHON = str(TARGET_ROOT / ".venv" / ("Scripts/python.exe" if os.name == "nt"'
               ' else "bin/python"))\n')
    (scripts / "bad_site.py").write_text(old_spelling, encoding="utf-8")
    (scripts / "good_site.py").write_text(derived, encoding="utf-8")

    scanned = {path.relative_to(tmp_path).as_posix(): path.read_text(encoding="utf-8")
               for path in _active_python_files(tmp_path)}
    assert set(scanned) == {"scripts/bad_site.py", "scripts/good_site.py"}, sorted(scanned)
    hits = {name: sorted({m.group(0) for m in VENV_WINDOWS_ONLY_BUILD.finditer(text)})
            for name, text in scanned.items()}
    planted_hit = ['".venv" / "Scripts" / "python.exe']
    assert hits["scripts/bad_site.py"] == planted_hit, hits
    assert hits["scripts/good_site.py"] == [], hits


def _load_conftest():
    """``tests/conftest.py`` as a module, under a name pytest will not collect."""
    spec = importlib.util.spec_from_file_location(
        "conftest_under_test", TARGET_ROOT / "tests" / "conftest.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_a_session_leaves_no_forgotten_mkdtemp_sandbox(tmp_path):
    """The harness sweeps the sandboxes it made, and never touches the ones a document cites.

    Measured on 2026-11-03: every full-suite run left **80** directories under
    ``.project-local/task-runtime`` -- 1,040 of them, 286 MB -- because several legacy tests pass
    that project-owned root to ``mkdtemp`` as its parent and nothing removes the result. The other
    thing in this root is real: ``penpot-import``, ``kit-register`` and friends are named as
    evidence paths by tracked documents, so the population is (name matches, directory, created
    after the session snapshot) and all three conditions are planted for here.
    """
    conftest = _load_conftest()
    root = tmp_path / "task-runtime"
    root.mkdir()
    (root / "penpot-import").mkdir()          # named evidence directory: no claim on it
    (root / "tmpNotMine").mkdir()             # present when the session snapshot was taken
    (root / "tmpLeaked9000").mkdir()          # the leak this fixture exists to remove
    (root / "tmp_underscore7").mkdir()        # mkdtemp's alphabet includes "_" right after tmp
    (root / "tmpFileNotDir").write_text("not a directory\n", encoding="utf-8")

    created = conftest.sandboxes_created(root, {"tmpNotMine"})
    # a set, not a list: on Windows PurePath ordering folds case, so "tmp_..." sorts before
    # "tmpL..." there and after it on a POSIX runner -- which names are swept is the contract
    assert {path.name for path in created} == {"tmpLeaked9000", "tmp_underscore7"}, (
        "the sweep selected the wrong population: %s" % [path.name for path in created])

    removed, failed = conftest.remove_sandboxes(created)
    assert (removed, failed) == (2, []), (removed, failed)
    assert not (root / "tmpLeaked9000").exists(), "remove_sandboxes reported success it did not have"
    assert not (root / "tmp_underscore7").exists(), "the underscore name survived the sweep"
    assert (root / "penpot-import").is_dir() and (root / "tmpNotMine").is_dir(), (
        "the sweep deleted something outside its claim -- a cited evidence directory or one that "
        "existed before this session")
    assert (root / "tmpFileNotDir").is_file(), (
        "a plain file entered a directory-only population -- the sweep would have "
        "tried to rmtree something that is not a sandbox")
    assert "tmpFileNotDir" not in {path.name for path in created}, created

    (root / "tmpAlsoOld").mkdir()
    assert conftest.sandboxes_created(root, {"tmpNotMine", "tmpAlsoOld"}) == [], (
        "with every sandbox accounted for before the session, the sweep still found work: the "
        "snapshot is not what limits it")

    # the failure path is part of the contract: a sandbox that cannot be removed is reported, not
    # swallowed -- otherwise the sweep summary would say "cleaned" about a leak that is still there
    class _RaisingShutil:
        @staticmethod
        def rmtree(path, onerror=None):
            raise OSError(13, "planted: the sandbox is still open")

    real_shutil = conftest.shutil
    try:
        conftest.shutil = _RaisingShutil
        planted = [root / "tmpAlsoOld", root / "penpot-import"]
        removed, failed = conftest.remove_sandboxes(planted)
        assert (removed, failed) == (0, ["tmpAlsoOld", "penpot-import"]), (
            "a removal that always failed was reported as cleaned: %s" % ((removed, failed),))
    finally:
        conftest.shutil = real_shutil

    # the age floor is a second, independent guard: a matching directory that predates the session
    # is not this session's to remove, even when the snapshot says nothing about it. This exists
    # because a falsification run on 2026-11-03 mutated away the snapshot check inside a live
    # session and deleted 1,041 sandboxes that had accumulated before that run started.
    (root / "tmpPredatesSession").mkdir()
    backdated = time.time() - 86400
    os.utime(root / "tmpPredatesSession", (backdated, backdated))
    fresh = root / "tmpFreshOne"
    fresh.mkdir()
    floor = fresh.stat().st_mtime - 1.0
    selected = {path.name for path in conftest.sandboxes_created(root, set(), floor)}
    assert "tmpFreshOne" in selected, selected
    assert "tmpPredatesSession" not in selected, (
        "the age floor did not exclude a directory that predates the session -- the snapshot is "
        "the only thing limiting it, and one dropped condition is enough to eat the residue")

    # the pattern has to match the names this repository actually leaked (read off the disk on
    # 2026-11-03, kept here so the check stays meaningful after the residue is swept away)
    actually_leaked = ["tmpxquepdl8", "tmpfjrsydpt", "tmpzxhlp0z_", "tmpv5_6kp7r", "tmp_s1j7k3i"]
    cited_by_a_document = ["penpot-import", "kit-register", "reconstruction", "asset-analysis",
                           "assurance-jury-tests", "browser-fixture"]
    assert all(conftest.SANDBOX_NAME.match(name) for name in actually_leaked), actually_leaked
    assert [name for name in cited_by_a_document
            if conftest.SANDBOX_NAME.match(name)] == [], cited_by_a_document

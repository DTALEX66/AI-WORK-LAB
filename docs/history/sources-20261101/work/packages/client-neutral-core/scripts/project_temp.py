"""Throwaway fixture roots that cannot land outside the project Git root.

ERR-140 was a bare ``tempfile.mkdtemp()`` in a governance test: its ``tearDown`` did
``shutil.rmtree(..., ignore_errors=True)``, so a failing run left complete mirrors of the authority
package in the system temp directory — outside the boundary
``.project/governance/project-data-boundary.json`` declares ("all content this project produces —
builds, caches, temp files, evidence … stays locked inside the project Git root").

The canonical gate runner binds ``TMP``/``TEMP``/``TMPDIR`` to ``.project-local/runs/tmp`` for its
children, so a fixture created *inside a gate run* is already contained. This module removes the
dependence on that environment for paths production code creates when it is invoked directly, and it
deliberately exposes one entry point named ``fixture_dir`` rather than ``mkdtemp``: the debt gate
``tests/workflow-assistance/test_temp_fixture_stays_inside_the_boundary.py`` fails on any call whose
name is ``mkdtemp`` without ``dir=``, so a bounded helper must not be able to masquerade as the leak it
replaces.

The other half is release. ``git`` writes ``.git/objects/xx/*`` with mode 0444, so a plain
``shutil.rmtree`` of a fixture that ran ``git commit`` stops with WinError 5 on Windows, and
``ignore_errors=True`` hid that completely: measured 2026-10-08, ``.project-local/runs/tmp`` held 4811
leftover fixture roots / 531.7 MiB, 676 of them still containing a nested ``.git``. ``force_release``
below is the one implementation that clears the read-only bits before deleting, and every fixture
release goes through it.

That still leaves orphans: the at-exit sweep only knows about the fixtures *this* process created, so a
run that is killed, times out or crashes leaves its roots behind with no owner. Nothing reclaimed them
until ``scripts/maintenance/release_temp_fixture_residue.py``, and the bound gate
``tests/ci/test_temp_fixture_residue_is_bounded.py`` now refuses to let that pile up again.
"""
from __future__ import annotations

import atexit
import gc
import json
import os
import shutil
import stat
import sys
import tempfile
from contextlib import contextmanager
from pathlib import Path

if str(Path(__file__).resolve().parent) not in sys.path:
    sys.path.insert(0, str(Path(__file__).resolve().parent))

from evidence_range_reader import name_is_sensitive  # noqa: E402

REPO_ROOT = Path(__file__).resolve().parents[3]
DEFAULT_TMP = REPO_ROOT / ".project-local" / "runs" / "tmp"
BOUNDARY_FILE = REPO_ROOT / ".project" / "governance" / "project-data-boundary.json"


def declared_runtime_root() -> Path:
    """The runtime root the data-boundary contract declares, resolved against this repository.

    Read from the machine authority rather than hardcoded, because a CLI default that points at
    ``%TEMP%`` writes canonical state (``canonical.sqlite``) outside the project root, which AGENTS.md
    and ``project-data-boundary.json`` forbid.
    """
    declared = json.loads(BOUNDARY_FILE.read_text(encoding="utf-8"))["runtimeRoot"]
    root = (REPO_ROOT / declared).resolve()
    if not root.is_relative_to(REPO_ROOT):
        raise RuntimeError(f"RUNTIME_ROOT_ESCAPES_PROJECT {root} (declared {declared!r})")
    return root


def runtime_dir(name: str) -> Path:
    """A named durable runtime directory inside the declared root -- worker stores and CLI defaults."""
    root = declared_runtime_root()
    target = (root / name).resolve()
    if not target.is_relative_to(root):
        raise RuntimeError(f"RUNTIME_ROOT_ESCAPES_PROJECT {target}")
    target.mkdir(parents=True, exist_ok=True)
    return target


@contextmanager
def fixture_root(prefix: str = "work-lab-"):
    """A `with` fixture directory that stays inside the boundary and is released on exit.

    ``tempfile.TemporaryDirectory()`` deletes itself -- until cleanup fails, which on Windows is exactly
    what a still-open ``canonical.sqlite`` handle does. Measured 2026-10-10 in the user temp root:
    25 ``tmp*`` directories holding 2 canonical stores, 18 git-metadata files and 6,495,636 B, and 5 more
    in ``C:\\Windows\\TEMP``. ``fixture_dir`` + ``force_release`` reports a refusal instead of swallowing
    it, and the root is inside the declared runtime root either way.
    """
    path = fixture_dir(prefix=prefix)
    try:
        yield path
    finally:
        force_release(path)


def require_runtime_root(value: Path | None, name: str) -> Path:
    """Resolve a caller-supplied runtime root, refusing one that leaves the project.

    A worker store written outside the repository is invisible to the boundary sweep and survives the
    checkout, so the CLI cannot accept whatever it is handed; the refusal is named, not silent.
    """
    if value is None:
        return runtime_dir(name)
    resolved = Path(value).resolve()
    if not resolved.is_relative_to(REPO_ROOT):
        raise RuntimeError(f"RUNTIME_ROOT_ESCAPES_PROJECT {resolved} "
                           f"(declared runtime root: {declared_runtime_root()})")
    resolved.mkdir(parents=True, exist_ok=True)
    return resolved


def temp_root() -> Path:
    """A writable in-boundary directory for throwaway fixtures.

    An inherited ``TMPDIR``/``TEMP``/``TMP`` is honoured only when it resolves inside the repository;
    anything else (system temp, a path that cannot be resolved) is refused and the project-local root
    is used instead. A boundary gate fails closed — it does not take the environment's word for it.
    """
    for variable in ("TMPDIR", "TEMP", "TMP"):
        raw = os.environ.get(variable)
        if not raw:
            continue
        candidate = Path(raw)
        try:
            resolved = candidate.resolve()
        except OSError:
            continue
        if resolved.is_relative_to(REPO_ROOT):
            resolved.mkdir(parents=True, exist_ok=True)
            return resolved
    DEFAULT_TMP.mkdir(parents=True, exist_ok=True)
    return DEFAULT_TMP


_TRACKED: list[Path] = []
_SWEEP_REGISTERED = False

# Consecutive refused names mean the prefix itself is a sensitive kind, not that luck has run out.
_NAME_ATTEMPTS = 5


def _clear_read_only_bits(root: Path) -> None:
    """Make everything under ``root`` deletable without following links out of it.

    Symlinks and junctions are skipped: clearing the bits on a target would write outside the
    fixture, which is the opposite of what a cleanup is for.
    """
    for dirpath, dirnames, filenames in os.walk(root):
        for name in [*dirnames, *filenames]:
            target = Path(dirpath) / name
            try:
                if target.is_symlink() or os.access(target, os.W_OK):
                    continue
                target.chmod(stat.S_IWRITE)
            except OSError:
                pass  # the rmtree below reports whatever this leaves undeletable


def force_release(path: Path) -> bool:
    """Delete a fixture root, clearing git's read-only object bits first. True when it is gone.

    Refuses any path outside the project Git root, and reports a release that still cannot finish
    with the ``TEMP_RESIDUE_NOT_REMOVED`` token instead of ignoring it. An open handle (a store that
    was never closed) is the caller's to fix — this cannot close it, and says so.
    """
    if not path.exists():
        return True
    if not inside_project(path):
        print(f"TEMP_RESIDUE_NOT_REMOVED {path} RefusalError: fixture root is outside the project")
        return False
    _clear_read_only_bits(path)
    gc.collect()  # a store left inside a reference cycle keeps its handle open (WinError 32)
    try:
        shutil.rmtree(path)
    except OSError as error:  # reported, never ignored — residue must be visible
        print(f"TEMP_RESIDUE_NOT_REMOVED {path} {type(error).__name__}: {error}")
        return False
    return True


def _release_tracked() -> None:
    for leftover in list(_TRACKED):
        if force_release(leftover):
            _TRACKED.remove(leftover)


def fixture_dir(prefix: str = "work-lab-") -> Path:
    """Create a throwaway directory inside the boundary and guarantee its release is attempted.

    A self-check script that makes five fixture roots and forgets five ``rmtree`` calls is the ERR-140
    spill. Registration here is part of creation, so cleanup cannot be forgotten, and a removal that
    fails is reported rather than swallowed. On Windows a fixture whose store is still open cannot be
    removed, so a caller that opens a database must close it — the report names the directory instead
    of hiding it.

    The name is checked before the root is handed out. ``mkdtemp`` appends eight random characters drawn
    from ``[a-z0-9_]``, and the evidence reader splits every path component on the non-alphanumerics, so a
    suffix shaped like ``_db_`` makes the fixture root *itself* a ``SENSITIVE_NAME`` handle — and because
    the reader judges every ancestor too, everything created under that root is refused with it. Measured
    2026-10-08: one generated root in 20,000 collides, all of them through the two-letter token ``db``.
    The reader's rule is the law and is not loosened for convenience; the helper that mints the name asks
    it, discards a refused root through ``force_release``, and tries again.
    """
    global _SWEEP_REGISTERED
    root = temp_root()
    for _ in range(_NAME_ATTEMPTS):
        path = Path(tempfile.mkdtemp(prefix=prefix, dir=str(root)))
        if not path.is_relative_to(REPO_ROOT):
            raise RuntimeError(f"fixture root escaped the project boundary: {path}")
        if not name_is_sensitive(Path(path.name)):
            break
        if not force_release(path):
            raise RuntimeError(f"a refused fixture root could not be released: {path}")
    else:
        raise RuntimeError(
            f"{_NAME_ATTEMPTS} consecutive fixture names under {root} were refused by the evidence reader, "
            f"so the prefix {prefix!r} itself names a sensitive kind; the reader cannot read anything created "
            f"under it and the caller must choose a prefix it accepts."
        )
    _TRACKED.append(path)
    if not _SWEEP_REGISTERED:
        atexit.register(_release_tracked)
        _SWEEP_REGISTERED = True
    return path


def pending_fixtures() -> tuple[Path, ...]:
    return tuple(_TRACKED)


def inside_project(path: Path) -> bool:
    try:
        return path.resolve().is_relative_to(REPO_ROOT)
    except OSError:
        return False

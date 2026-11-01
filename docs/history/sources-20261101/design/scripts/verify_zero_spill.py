#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""DLDS-E010 — zero-spill future gate.

A DESIGN-LAB task may write only inside the repository's tracked/authorized tree,
inside ``.project-local``, or inside an explicitly declared external cache. A file
that appears anywhere else is `SPILL_DETECTED`.

The gate works by snapshot and diff, because "we did not spill" is only provable
by comparing the file system before and after the work:

    python scripts/verify_zero_spill.py --snapshot before
    <run the DESIGN-LAB task>
    python scripts/verify_zero_spill.py --diff before

Agent homes are observed at path level only. Their contents are never read, and
entries the agent owns (sessions, memory, credentials) are excluded from the
comparison by name so that the harness's own bookkeeping is not reported as a
DESIGN-LAB spill.

DL-AUDIT-20260914-03 hardens the gate:

* path-level inventories are normalized and link/junction-boundary aware: a
  directory that is a reparse point is never traversed, so a link cannot pull
  the observation out of its declared root;
* agent-state roots inside the repository (``.hermes``, ``.openhuman``) are
  denied write scope: a new file under the repository ``.hermes`` is spill even
  though it sits under the repository root;
* forbidden project run directories (old runtime roots outside the repository)
  may be declared with ``--external DIR`` on BOTH snapshot and diff; for those,
  any new, modified or removed file is a spill, while the repository and
  ``.project-local`` remain the allowed roots;
* a depth cut or the entry cap makes the observation INCOMPLETE: the diff then
  reports ``ZERO_SPILL=INCOMPLETE`` instead of claiming zero spill, because a
  truncated observation cannot bound what it did not see.

Usage:
    python scripts/verify_zero_spill.py --snapshot ID [--external DIR]...
    python scripts/verify_zero_spill.py --diff ID
    python scripts/verify_zero_spill.py --self-test
"""
from __future__ import annotations

import argparse
import json
import os
import subprocess
from datetime import datetime, timezone
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
SNAPSHOT_DIR = REPO / ".project-local/task-artifacts/zero-spill"
TASK_KEY = "DL-TP-20260914-DEEPSEEK-AUTHORITY-R1::DLDS-E010"
HOME = Path(os.environ.get("USERPROFILE", Path.home()))
# Roots whose changes are allowed for a DESIGN-LAB task.
ALLOWED_ROOTS = (REPO, REPO / ".project-local")
# Observed but not allowed to change.
WATCHED_AGENT_HOMES = {".hermes": "Hermes", ".codex": "Codex", ".dsh": "DSH"}
AGENT_NATIVE_NAMES = {"sessions", "archived_sessions", "memories", "memory", "log", "logs", "tmp",
                      ".tmp", "cache", "browser", "attachments", "task-board", "storages",
                      "generated_images", "computer-use", "marketplaces", "automations",
                      "dictation-history", "profiles", "plugins", "desktop-plugins", "skin-center",
                      "sandbox", ".sandbox", ".sandbox-bin", ".sandbox-secrets", "agent-presets",
                      ".agent-presets"}
SKIP_DIRS = {".git", ".venv", "node_modules", "__pycache__", ".pytest_cache", ".mypy_cache"}
# Agent-state roots inside the repository: DESIGN-LAB work may never write here.
# They are observed at path level only (never read), like the external agent
# homes, and any change under them inside the repository is a spill.
DENIED_REPO_ROOTS = {".hermes", ".openhuman", ".codex", ".dsh"}
MAX_ENTRIES = 200_000


def _is_reparse(path: Path) -> bool:
    """True when the path is a Windows junction / reparse point (symlinks are
    already handled by Path semantics on POSIX). A link directory must never be
    traversed: following it would pull the observation outside its declared
    root and silently widen the observed surface."""
    if not path.is_symlink():
        try:
            import ctypes
            attrs = ctypes.windll.kernel32.GetFileAttributesW(str(path))
            if attrs == 0xFFFFFFFF:  # INVALID_FILE_ATTRIBUTES
                return False
            return bool(attrs & 0x800)  # FILE_ATTRIBUTE_REPARSE_POINT
        except (AttributeError, OSError):
            return False
    return True


def scan(root: Path, *, depth: int = 3) -> tuple[dict, bool, list]:
    """Path-level inventory: relative path -> (size, mtime). Never reads content.

    Returns (entries, complete, link_boundaries). ``complete`` is False when the
    depth cut, the entry cap, an untraversed reparse point, or a directory/file
    we could not stat due to permissions truncated the walk; ``link_boundaries``
    lists the boundary paths (unfollowed links/junctions, BLOCKED entries) that
    explain an INCOMPLETE verdict so it can be located.
    """
    entries = {}
    complete = True
    links: list[str] = []
    if not root.is_dir():
        return entries, True, links
    base_depth = len(root.parts)

    def _walk_error(err: OSError) -> None:
        # A directory whose contents we cannot list is unobserved territory: the
        # walk is truncated. Record it so an INCOMPLETE verdict can be located
        # (DL-UCR-013 / FA-05: a permission failure -> incomplete, never a
        # silent skip, because a silently skipped directory could hide a spill).
        nonlocal complete
        complete = False
        links.append(f"BLOCKED:{getattr(err, 'filename', None) or err}")

    for current, dirs, files in os.walk(root, onerror=_walk_error):
        current_path = Path(current)
        over_depth = len(current_path.parts) - base_depth >= depth
        # A reparse-point directory must not be followed (junction/link boundary).
        kept_dirs = []
        for name in dirs:
            if name in SKIP_DIRS:
                continue
            if _is_reparse(current_path / name):
                complete = False  # unseen territory; flag INCOMPLETE, do not traverse
                links.append(str(current_path / name))
                continue
            kept_dirs.append(name)
        if over_depth:
            complete = False  # truncated by depth: remainder unobserved
        dirs[:] = kept_dirs
        for name in files + kept_dirs:
            path = current_path / name
            try:
                stat = path.stat(follow_symlinks=False)
            except PermissionError:
                # Access to a real entry was denied: the observation is truncated.
                # Do not treat it as "no file" (that would let it hide a spill).
                complete = False
                links.append(f"BLOCKED:{path}")
            except OSError:
                # A broken/replaced entry (ENOENT): nothing to observe.
                continue
            else:
                entries[str(path)] = [stat.st_size, int(stat.st_mtime)]
            if len(entries) > MAX_ENTRIES:
                return entries, False, links
    return entries, complete, links


def declared_external_roots() -> tuple[str, ...]:
    """The external roots this project declares in `.project/paths.json`.

    Forbidden run directories were only ever accepted through `--external`, and
    nothing read the declaration, so a default invocation reported
    `external_roots=0` and could not certify the shared library roots at all --
    which is precisely why the flag never got passed and the guard quietly
    covered less than it appeared to.
    """
    paths_file = REPO / ".project" / "paths.json"
    try:
        doc = json.loads(paths_file.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return ()
    shared = doc.get("shared_inputs") if isinstance(doc, dict) else None
    if not isinstance(shared, dict):
        return ()
    return tuple(str(v) for v in shared.values() if isinstance(v, str) and v.strip())


def snapshot(snapshot_id: str, externals: tuple | None = None) -> int:
    SNAPSHOT_DIR.mkdir(parents=True, exist_ok=True)
    externals = [Path(x) for x in (externals or ())]
    repo_entries, repo_complete, repo_links = scan(REPO, depth=8)
    document = {
        "schemaVersion": "design-lab/zero-spill-snapshot/v2",
        "task_key": TASK_KEY,
        "snapshot_id": snapshot_id,
        "taken_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "subject_sha": subprocess.run(["git", "-C", str(REPO), "rev-parse", "HEAD"],
                                      capture_output=True, text=True,
                                      encoding="utf-8").stdout.strip(),
        "repo": repo_entries,
        "repo_complete": repo_complete,
        "repo_link_boundaries": repo_links,
        "denied_repo_roots": sorted(DENIED_REPO_ROOTS),
        "agent_homes": {},
        "agent_homes_complete": {},
        "external_forbidden": {},
        "external_forbidden_complete": {},
    }
    for name in WATCHED_AGENT_HOMES:
        entries, complete, _links = scan(HOME / name, depth=2)
        document["agent_homes"][name] = entries
        document["agent_homes_complete"][name] = complete
    for external in externals:
        resolved = external.resolve()
        entries, complete, _links = scan(resolved, depth=8)
        if not resolved.is_dir():
            # A declared root that is not present on this machine observed
            # nothing. scan() returns an empty inventory with complete=True for a
            # missing path, which would let "not installed here" be read as
            # "no spill here"; the verdict has to stay INCOMPLETE instead.
            complete = False
        document["external_forbidden"][str(external)] = entries
        document["external_forbidden_complete"][str(external)] = complete
    path = SNAPSHOT_DIR / f"{snapshot_id}.json"
    path.write_text(json.dumps(document, ensure_ascii=False) + "\n", encoding="utf-8", newline="\n")
    print(f"ZERO_SPILL_SNAPSHOT={snapshot_id} repo_entries={len(document['repo'])} "
          f"repo_complete={repo_complete} "
          f"agent_entries={sum(len(v) for v in document['agent_homes'].values())} "
          f"external_roots={len(externals)} file={path.relative_to(REPO)}")
    return 0


def allowed(path: str) -> bool:
    candidate = Path(path)
    for root in ALLOWED_ROOTS:
        try:
            candidate.relative_to(root)
            return True
        except ValueError:
            continue
    return False


def _denied_repo_root(path: str) -> str | None:
    """A path that lies under a denied in-repo agent-state root (e.g. .hermes)."""
    try:
        relative = Path(path).relative_to(REPO)
    except ValueError:
        return None
    top = relative.parts[0]
    if top in DENIED_REPO_ROOTS:
        return top
    return None


def diff(snapshot_id: str, externals: tuple | None = None) -> int:
    path = SNAPSHOT_DIR / f"{snapshot_id}.json"
    if not path.is_file():
        print(f"ZERO_SPILL=FAIL missing snapshot {snapshot_id}")
        return 1
    before = json.loads(path.read_text(encoding="utf-8"))
    subject_sha = subprocess.run(["git", "-C", str(REPO), "rev-parse", "HEAD"], capture_output=True,
                                 text=True, encoding="utf-8").stdout.strip()
    incomplete = []
    if not before.get("repo_complete", True):
        incomplete.append("repo")
    for name, complete in before.get("agent_homes_complete", {}).items():
        if not complete:
            incomplete.append(f"agent:{name}")
    for external, complete in before.get("external_forbidden_complete", {}).items():
        if not complete:
            incomplete.append(f"external:{external}")

    report = {"schemaVersion": "design-lab/zero-spill-diff/v2", "task_key": TASK_KEY,
              "snapshot_id": snapshot_id, "compared_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
              "snapshot_sha": before["subject_sha"], "current_sha": subject_sha,
              "same_subject": before["subject_sha"] == subject_sha,
              "roots": {}}
    spill = []

    # Repository root: allowed to change inside .project-local, denied inside
    # agent-state roots, spill anywhere else.
    current_repo, repo_complete, _repo_links = scan(REPO, depth=8)
    previous = before["repo"]
    if not repo_complete:
        incomplete.append("repo-current")
    new = sorted(set(current_repo) - set(previous))
    removed = sorted(set(previous) - set(current_repo))
    changed = sorted(p for p in set(current_repo) & set(previous) if current_repo[p] != previous[p])
    # Denied in-repo agent-state roots take priority over the allowed root
    # (DL-UCR-013 / FA-05: denied -> allowed -> unknown). A NEW file under
    # .hermes/.codex/... is spill even though it sits under the repository
    # root; only a path that is neither denied nor outside the allowed roots
    # is exempt.
    repo_spill = []
    for candidate in new:
        if _denied_repo_root(candidate) is not None:
            repo_spill.append(candidate)
            continue
        if allowed(candidate):
            continue
        repo_spill.append(candidate)  # outside the allowed roots
    # Modifying a pre-existing file inside a denied in-repo root is also spill.
    for candidate in changed:
        if _denied_repo_root(candidate) is not None:
            repo_spill.append(f"MODIFIED:{candidate}")
    # A removed file is reported, not a spill: the task did not create it.
    report["roots"]["repo"] = {"new": len(new), "removed": len(removed), "changed": len(changed),
                               "spill": repo_spill[:50], "exempt": False}
    spill.extend(repo_spill)

    # Agent homes: observed at path level; native bookkeeping names are exempt.
    for name in WATCHED_AGENT_HOMES:
        current = scan(HOME / name, depth=2)[0]
        previous = before["agent_homes"].get(name, {})
        new = sorted(set(current) - set(previous))
        removed = sorted(set(previous) - set(current))
        changed = sorted(p for p in set(current) & set(previous) if current[p] != previous[p])
        root_spill = [c for c in new if Path(c).name not in AGENT_NATIVE_NAMES]
        report["roots"][f"agent:{name}"] = {"new": len(new), "removed": len(removed),
                                             "changed": len(changed), "spill": root_spill[:50], "exempt": True}
        spill.extend(root_spill)

    # Forbidden external run directories: any new, modified or removed entry is
    # a spill. These are the "old project run directories" that must not move.
    declared = list(before.get("external_forbidden", {}).keys())
    for external in (externals or declared):
        key = str(Path(external).resolve())
        current = scan(Path(key), depth=8)[0] if Path(key).is_dir() else {}
        previous = before.get("external_forbidden", {}).get(
            key, before.get("external_forbidden", {}).get(str(external), {}))
        new = sorted(set(current) - set(previous))
        removed = sorted(set(previous) - set(current))
        changed = sorted(p for p in set(current) & set(previous) if current[p] != previous[p])
        root_spill = new + [f"MODIFIED:{p}" for p in changed] + [f"REMOVED:{p}" for p in removed]
        report["roots"][f"external:{key}"] = {"new": len(new), "removed": len(removed),
                                               "changed": len(changed), "spill": root_spill[:50], "exempt": False}
        spill.extend(root_spill)

    report["incomplete_roots"] = sorted(set(incomplete))
    report["observation_complete"] = not incomplete
    report["spill_total"] = len(spill)
    if incomplete:
        report["verdict"] = "ZERO_SPILL=INCOMPLETE"
        report["meaning"] = ("a truncated or link-boundary observation cannot claim zero spill; "
                             "the unobserved remainder is listed in incomplete_roots")
    else:
        report["verdict"] = "NO_SPILL_DETECTED" if not spill else "SPILL_DETECTED"
        report["meaning"] = ("paths outside the repository, .project-local and the declared external "
                             "caches; agent-native bookkeeping names are excluded; in-repo agent-state "
                             "roots are denied write scope")
    (SNAPSHOT_DIR / f"{snapshot_id}-diff.json").write_text(
        json.dumps(report, indent=2, ensure_ascii=False) + "\n", encoding="utf-8", newline="\n")
    print(f"ZERO_SPILL={report['verdict']} spill={len(spill)} "
          f"repo_new={report['roots']['repo']['new']} repo_changed={report['roots']['repo']['changed']} "
          f"incomplete_roots={report['incomplete_roots'] or 'none'}")
    for item in spill[:10]:
        print("  SPILL:", item)
    if incomplete:
        return 2
    return 0 if not spill else 1


def resolve_interpreter() -> tuple[str, bool]:
    """Pick the project interpreter without assuming a Windows layout.

    (DL-AUDIT-20260914-06) The gate no longer hard-codes
    ``.venv/Scripts/python.exe``: it resolves the running interpreter first,
    then the platform-appropriate virtualenv, and only falls back to ``python3``.
    Returns (command, resolved).
    """
    import sys
    candidates = [sys.executable]
    for name in (".venv/Scripts/python.exe", ".venv/bin/python"):
        candidate = REPO / name
        if candidate.exists():
            candidates.append(str(candidate))
    candidates.append("python3")
    for candidate in candidates:
        if candidate == "python3":
            return candidate, True
        if Path(candidate).exists():
            return candidate, True
    return "python3", True


def self_test(externals: tuple | None = None) -> int:
    """Run a real read-only DESIGN-LAB command between two snapshots.

    The command's exit code is part of the evidence. A command that failed may have
    aborted before it did any work, so it proves nothing about spill; an INDEPENDENT
    AUDIT caught this self-test wrapping a ``--check`` that exited 1 and returning the
    spill verdict anyway. The task under test is therefore also required to succeed,
    which couples this self-test to the projection freshness gate: run
    ``scripts/generate_current_reports.py`` before it.
    """
    before_id = "self-test-before"
    if snapshot(before_id, externals) != 0:
        return 1
    interpreter, _ = resolve_interpreter()
    command = [interpreter,
               str(REPO / "scripts/generate_current_reports.py"), "--check"]
    result = subprocess.run(command, capture_output=True, text=True, encoding="utf-8",
                           cwd=str(REPO), timeout=300)
    print(f"  task under test: {' '.join(Path(part).name for part in command)} "
          f"exit={result.returncode}")
    spill = diff(before_id, externals)
    if result.returncode != 0:
        print(f"ZERO_SPILL_SELF_TEST=FAIL the task under test exited {result.returncode} "
              f"({result.stdout.strip().splitlines()[-1] if result.stdout.strip() else 'no output'}); "
              "a failing command cannot prove that a working command does not spill")
        return 1
    return spill


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--snapshot")
    group.add_argument("--diff")
    group.add_argument("--self-test", action="store_true")
    parser.add_argument("--external", action="append", default=None,
                        metavar="DIR",
                        help="additional forbidden project run directory; declare on snapshot AND diff")
    parser.add_argument("--no-declared-externals", action="store_true",
                        help="do not fold in the roots declared in .project/paths.json")
    args = parser.parse_args(argv)
    declared = () if args.no_declared_externals else declared_external_roots()
    externals = tuple(dict.fromkeys([*(args.external or ()), *declared]))
    if args.self_test:
        return self_test(externals)
    return snapshot(args.snapshot, externals) if args.snapshot else diff(args.diff, externals)


if __name__ == "__main__":
    raise SystemExit(main())

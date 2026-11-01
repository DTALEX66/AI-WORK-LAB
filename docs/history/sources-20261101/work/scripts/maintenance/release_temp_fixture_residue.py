"""Reclaim orphaned throwaway fixtures under the bounded temp root, keeping live ones in place.

`project_temp.fixture_dir()` registers each root it creates and releases them from an at-exit hook, so
a run that exits normally leaves nothing behind — measured 2026-10-08 by running
`tests/workflow-assistance/test_cleanup.py` (17 tests, 17 fixtures created and released, count
unchanged). What accumulates is a different thing: a gate job that is killed, times out or crashes
never reaches at-exit, and its fixtures then have **no owner at all**. Nothing in the repository
looked at them until now, so the root held 4811 directories / 531.7 MiB, 676 of them carrying a nested
`.git` whose mode-0444 object files made even an explicit `shutil.rmtree` fail (WinError 5) — a failure
that `ignore_errors=True` used to swallow.

Order of operations, because deletion is not reversible:

1. measure: every candidate directory, its size, its age, and its contents count;
2. write the manifest, then delete only what the manifest lists;
3. an age floor (`--older-than-hours`, default 6) protects a fixture belonging to a session that is
   running *right now* in this checkout — this tool must never be able to break a concurrent run;
4. release goes through `project_temp.force_release`, the one implementation that clears git's
   read-only bits and reports `TEMP_RESIDUE_NOT_REMOVED` instead of hiding a refusal.

`--apply` is required to delete; without it the tool is a dry run that writes the manifest only. The
bound gate `tests/ci/test_temp_fixture_residue_is_bounded.py` is what makes the pile un-regrowable.
Only paths inside the project Git root are eligible; anything else, including `E:\\` and `F:\\`, is
refused outright.

Two scratch families are censused, because a killed gate job leaves both behind and only one of them is a
`project_temp` fixture: the bounded temp root, and the per-run Chrome profile directories the geometry gate
creates under `.project-local/runs/geometry-gate/` (a browser that is killed mid-capture cannot clean its own
profile, and 2026-10-25 found one still sitting there). A profile is released only after its own age floor and
only through the same refusal-reporting path, so a live Chrome cannot lose a directory under its feet.

The manifest name carries the mode, a microsecond stamp and a collision counter, and every write is
create-exclusive: a dry run that lands in the same second as an applied release used to overwrite it and
erase the record of what was deleted (measured 2026-10-25 -- both runs printed the same manifest path).

Usage:
    python scripts/maintenance/release_temp_fixture_residue.py [--apply] [--older-than-hours N]
Exit: 0 dry run or completed release; 1 a candidate could not be released; 2 refused.
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import time
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO_ROOT / "packages" / "client-neutral-core" / "scripts"))
import project_temp  # noqa: E402

DEFAULT_ROOT = REPO_ROOT / ".project-local" / "runs" / "tmp"
# A second census root with a name filter: only these prefixes are browser scratch, and anything else that
# happens to live beside them stays out of reach of a deletion tool.
PROFILE_ROOT = REPO_ROOT / ".project-local" / "runs" / "geometry-gate"
PROFILE_PREFIXES = ("udf-", "chrome-profile", "profile-")
ARTIFACT_DIR = REPO_ROOT / ".project-local" / "artifacts" / "temp-residue-reclaim"
# The bound gate imports this same number, so the tool and the gate cannot drift apart.
DEFAULT_OLDER_THAN_HOURS = 6.0


def tree_stats(root: Path) -> tuple[int, int]:
    """(bytes, file_count) for everything under `root`, without following links out of it."""
    total = 0
    files = 0
    for dirpath, _dirnames, filenames in os.walk(root):
        for name in filenames:
            try:
                total += os.lstat(os.path.join(dirpath, name)).st_size
            except OSError:
                pass
            files += 1
    return total, files


def candidates(root: Path, older_than_hours: float, now: float,
               name_prefixes: tuple[str, ...] | None = None) -> list[dict]:
    out = []
    if not root.is_dir():
        return out
    for entry in sorted(os.scandir(root), key=lambda e: e.name):
        if entry.is_symlink() or not entry.is_dir(follow_symlinks=False):
            continue
        path = Path(entry.path)
        if name_prefixes and not path.name.startswith(name_prefixes):
            continue
        age_hours = (now - path.stat().st_mtime) / 3600.0
        if age_hours < older_than_hours:
            continue
        size, files = tree_stats(path)
        out.append({
            "path": str(path),
            "name": path.name,
            "bytes": size,
            "files": files,
            "age_hours": round(age_hours, 3),
            "has_nested_git": any(".git" in dirnames for _r, dirnames, _f in os.walk(path)),
        })
    return out


def write_manifest(artifact_dir: Path, mode: str, stamp: str, payload: dict) -> Path:
    """Create a new manifest, never overwrite an existing one.

    The name carries the mode, a microsecond stamp and a counter, and the file is opened create-exclusive:
    a second-granularity stamp let a dry run land on an applied release's own path and replace the record of
    what had been deleted, which is the one thing this file exists to preserve.
    """
    artifact_dir.mkdir(parents=True, exist_ok=True)
    for attempt in range(1000):
        path = artifact_dir / f"manifest-{stamp}-{attempt:03d}-{mode}.json"
        try:
            with path.open("x", encoding="utf-8") as handle:
                json.dump(payload, handle, indent=2, ensure_ascii=False)
            return path
        except FileExistsError:
            continue
    raise RuntimeError(f"TEMP_RESIDUE_REFUSED could not allocate a unique manifest name in {artifact_dir}")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--apply", action="store_true", help="delete the listed candidates")
    parser.add_argument("--older-than-hours", type=float, default=DEFAULT_OLDER_THAN_HOURS,
                        help="skip anything newer than this so a concurrent run keeps its fixtures")
    parser.add_argument("--root", type=Path, default=None,
                        help="census only this root (the bounded temp root plus the gate's browser-profile "
                             "scratch are both scanned by default; naming a root is what the bound gate uses "
                             "to point the tool at a fixture tree of its own)")
    args = parser.parse_args()

    explicit_root = args.root is not None
    root = (args.root if explicit_root else DEFAULT_ROOT).resolve()
    if not project_temp.inside_project(root):
        print(f"TEMP_RESIDUE_REFUSED root={root} is outside the project Git root")
        return 2
    if not root.is_dir():
        print(f"TEMP_RESIDUE_NO_ROOT {root} does not exist")
        return 0

    now = time.time()
    rows = candidates(root, args.older_than_hours, now)
    profiles = [] if explicit_root else candidates(PROFILE_ROOT, args.older_than_hours, now,
                                                   PROFILE_PREFIXES)
    rows = rows + profiles
    total_bytes = sum(row["bytes"] for row in rows)
    print(f"TEMP_RESIDUE_CENSUS root={root} dirs={len(rows)} bytes={total_bytes} "
          f"mib={total_bytes / 1048576:.1f} nested_git={sum(1 for r in rows if r['has_nested_git'])} "
          f"browser_profiles={len(profiles)} older_than_hours={args.older_than_hours}")

    stamp = time.strftime("%Y%m%dT%H%M%SZ", time.gmtime(now)) + f"-{int(now * 1_000_000) % 1_000_000:06d}"
    manifest = write_manifest(ARTIFACT_DIR, "dry" if not args.apply else "apply", stamp, {
        "schema": "work-lab/temp-fixture-residue/v1",
        "root": str(root),
        "older_than_hours": args.older_than_hours,
        "captured_at": stamp,
        "apply": bool(args.apply),
        "dirs": len(rows),
        "bytes": total_bytes,
        "candidates": rows,
        "released": [],
        "failures": [],
    })
    print(f"TEMP_RESIDUE_MANIFEST {manifest}")

    if not args.apply:
        print("TEMP_RESIDUE_DRY_RUN dirs=%d bytes=%d apply_not_run=1" % (len(rows), total_bytes))
        return 0

    released, failures = [], []
    for row in rows:
        path = Path(row["path"])
        if project_temp.force_release(path):
            released.append(row)
        else:
            failures.append(row)

    payload = json.loads(manifest.read_text(encoding="utf-8"))
    payload["released"] = [{"path": r["path"], "bytes": r["bytes"]} for r in released]
    payload["failures"] = [{"path": r["path"], "bytes": r["bytes"]} for r in failures]
    payload["freed_bytes"] = sum(r["bytes"] for r in released)
    manifest.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")

    print(f"TEMP_RESIDUE_RECLAIM applied=1 dirs={len(released)} freed_bytes={payload['freed_bytes']} "
          f"freed_mib={payload['freed_bytes'] / 1048576:.1f} failures={len(failures)} "
          f"manifest={manifest}")
    return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(main())

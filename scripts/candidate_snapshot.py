# SPDX-License-Identifier: MIT
"""The canonical candidate-manifest 口径, as a callable and a CLI.

WHY THIS FILE EXISTS
    `docs/CODEX-AUDIT-ENTRY.md` section 6 defines the candidate digest as
    "Git cached + non-ignored untracked" path -> file SHA-256, and warns against
    mixing that with a "tracked only" reading. Until now that definition lived
    only in two throwaway copies under the gitignored `.project-local/`
    (`audit/20261030-qoder-ed9037/build_closure.py::candidate()` and
    `push-20261031/push_tools.py::candidate_state()`), so a fresh clone could
    neither reproduce nor check the digest the audit was bound to. This module is
    the tracked implementation of the same 口径, byte-for-byte equivalent.

THE 口径 (section 6, restated exactly)
    * enumeration: `git ls-files --cached --others --exclude-standard -z` run at
      the repository root, i.e. what is staged/committed plus what is untracked
      but not gitignored;
    * excluded path components: `.mimosa`, `__pycache__`, `.pytest_cache`
      (any path part, so a nested cache directory is skipped too);
    * value per path: the SHA-256 of the file's raw bytes, or the literal string
      "MISSING" for an enumerated path that is not a readable file (a symlink to
      nothing, or an entry deleted after listing);
    * digest: the SHA-256 of `json.dumps(mapping, sort_keys=True)` encoded UTF-8.

    A second, distinctly named reading -- `tracked_state()`, `git ls-files
    --cached` only -- exists here because section 6 forbids confusing the two.
    They are NOT interchangeable and generally do NOT agree; callers must say
    which one produced a number.

Reproducibility: running this file twice against an unchanged tree yields the same
digest, and that digest equals what `build_closure.candidate()` computes for the
same tree. Nothing here writes outside the path given to `--json-out`.

Usage
    python -B -X utf8 scripts/candidate_snapshot.py
    python -B -X utf8 scripts/candidate_snapshot.py --json-out <path>
    python -B -X utf8 scripts/candidate_snapshot.py --口径 tracked-only
    python -B -X utf8 scripts/candidate_snapshot.py --compare-with <snapshot.json>
"""
from __future__ import annotations

import argparse
import datetime
import hashlib
import json
import pathlib
import subprocess

REPO_ROOT = pathlib.Path(__file__).resolve().parents[1]
SKIP_PARTS = {".mimosa", "__pycache__", ".pytest_cache"}

CANDIDATE_口径 = "git_cached_plus_non_ignored_untracked"
TRACKED_ONLY_口径 = "git_tracked_only"
口径_NAMES = (CANDIDATE_口径, TRACKED_ONLY_口径)


def _git_ls_files(root: pathlib.Path, extra_args: list[str]) -> list[str]:
    listed = subprocess.check_output(
        ["git", "ls-files", *extra_args, "-z"], cwd=str(root))
    return [rel for rel in sorted(x for x in listed.decode("utf-8").split("\0") if x)]


def _digest_file(path: pathlib.Path) -> str:
    try:
        return hashlib.sha256(path.read_bytes()).hexdigest()
    except OSError:
        return "MISSING"


def _state(root: pathlib.Path, paths: list[str]) -> dict[str, str]:
    state: dict[str, str] = {}
    for rel in paths:
        if any(part in SKIP_PARTS for part in pathlib.PurePosixPath(rel).parts):
            continue
        state[rel] = _digest_file(root / rel)
    return state


def candidate_state(root: pathlib.Path | None = None) -> dict[str, str]:
    """The section-6 candidate 口径: Git cached plus non-ignored untracked."""
    root = pathlib.Path(root) if root is not None else REPO_ROOT
    paths = _git_ls_files(root, ["--cached", "--others", "--exclude-standard"])
    return _state(root, paths)


def tracked_state(root: pathlib.Path | None = None) -> dict[str, str]:
    """The other 口径 section 6 names: tracked (Git cached) entries only."""
    root = pathlib.Path(root) if root is not None else REPO_ROOT
    paths = _git_ls_files(root, ["--cached"])
    return _state(root, paths)


def state_for(name: str, root: pathlib.Path | None = None) -> dict[str, str]:
    if name == CANDIDATE_口径:
        return candidate_state(root)
    if name == TRACKED_ONLY_口径:
        return tracked_state(root)
    raise ValueError("unknown 口径 %r; expected one of %s" % (name, list(口径_NAMES)))


def digest_of(state: dict[str, str]) -> str:
    """SHA-256 of json.dumps(state, sort_keys=True) as UTF-8 bytes (section 6)."""
    return hashlib.sha256(json.dumps(state, sort_keys=True).encode("utf-8")).hexdigest()


def snapshot(name: str = CANDIDATE_口径, root: pathlib.Path | None = None,
             label: str | None = None) -> dict:
    state = state_for(name, root)
    return {
        "generated_at": datetime.datetime.now(datetime.timezone.utc).isoformat(),
        "label": label,
        "口径": name,
        "root": str(pathlib.Path(root) if root is not None else REPO_ROOT),
        "files": len(state),
        "digest": digest_of(state),
        "state": state,
    }


def delta(previous: dict, current: dict) -> dict:
    before = previous.get("state") or {}
    after = current.get("state") or {}
    added = sorted(p for p in after if p not in before)
    removed = sorted(p for p in before if p not in after)
    changed = sorted(p for p in after if p in before and after[p] != before[p])
    return {"from_口径": previous.get("口径"), "to_口径": current.get("口径"),
            "from_digest": previous.get("digest"), "to_digest": current.get("digest"),
            "added": added, "removed": removed, "changed": changed}


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Recompute the section-6 candidate manifest.")
    parser.add_argument("--json-out", default=None,
                        help="write the full snapshot here (default: print a summary only)")
    parser.add_argument("--label", default=None, help="a free-form label stored in the snapshot")
    parser.add_argument("--口径", "--kou-jing", dest="口径", default=CANDIDATE_口径,
                        choices=list(口径_NAMES),
                        help="which 口径 to apply; the default is the section-6 candidate one")
    parser.add_argument("--compare-with", default=None,
                        help="a previously written snapshot JSON to diff against")
    parser.add_argument("--root", default=None,
                        help="repository root to enumerate (default: this repo's parent of scripts/)")
    args = parser.parse_args(argv)

    root = pathlib.Path(args.root).resolve() if args.root else REPO_ROOT
    current = snapshot(args.口径, root, args.label)
    summary = {k: current[k] for k in ("口径", "root", "files", "digest")}

    if args.compare_with:
        previous = json.loads(pathlib.Path(args.compare_with).read_text(encoding="utf-8"))
        move = delta(previous, current)
        summary["compare_with"] = str(args.compare_with)
        summary["delta"] = {"from_口径": move["from_口径"], "to_口径": move["to_口径"],
                            "from_digest": move["from_digest"], "to_digest": move["to_digest"],
                            "added": len(move["added"]), "removed": len(move["removed"]),
                            "changed": len(move["changed"]),
                            "sample_paths": (move["added"] + move["removed"]
                                             + move["changed"])[:10]}

    if args.json_out:
        out = pathlib.Path(args.json_out)
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(json.dumps(current, ensure_ascii=False, indent=2) + "\n",
                       encoding="utf-8", newline="\n")
        summary["json_out"] = str(out)

    print(json.dumps(summary, ensure_ascii=True, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

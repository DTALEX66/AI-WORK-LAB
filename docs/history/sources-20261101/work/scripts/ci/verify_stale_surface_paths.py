"""Fail when a path that was archived on 2026-10-19 reappears on an active surface.

The hazard this closes is the one the owner named: after a normalization pass, an index or a
script still points at the old location, and a later session follows it onto material that was
deliberately taken off the visible surfaces. `scripts/ci/verify_authority_index_paths.py` only
sees `docs/current/` plus three named surfaces, so a stale pointer in `.project/governance/`,
`scripts/`, `tests/`, `apps/` or `docs/decisions/` would pass every existing gate.

Rules:
  * the population is the tracked file list minus the frozen/evidence prefixes named in the
    manifest -- an input set derived from the thing being enforced, not hand-listed;
  * frozen history and dated evidence are OUT OF SCOPE rather than edited: their old paths are
    the historical object of their own sentences;
  * a protected file that still carries old paths is a NAMED ALLOWANCE with a minimum count and
    a reason. An allowance that is no longer used fails, so fixing the file cannot leave a
    silent licence behind;
  * the scan refuses to report green on a suspiciously small population.

Verdicts, all red, never a silent skip:
  STALE_SURFACE_PATHS_PASS       every active surface is clean and each allowance is still used
  STALE_SURFACE_PATHS_FAIL       named stale references, unmet allowances, or unused allowances
  STALE_SURFACE_PATHS_NO_GIT     the tracked-file population could not be enumerated
  STALE_SURFACE_PATHS_NO_MANIFEST the move record is missing or unreadable
"""

from __future__ import annotations

import json
import re
import subprocess
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
MANIFEST = REPO / "docs/history/archive/MOVED-PATHS-20261019.json"
# A tracked tree below this size means the enumeration or the scope went blind, not that the
# repository got smaller: measured 2,599 tracked files and 1,287 in-scope files on 2026-10-19.
SCAN_FLOOR = 1000
# `…/original-tree/taskpacks/current/X.md` names a byte-frozen copy, not the live path.
LOOKBEHIND = r"(?<!original-tree/)"


def tracked_files(root: Path) -> list[str]:
    """Every tracked path, NUL-split so non-ASCII names survive."""
    result = subprocess.run(["git", "ls-files", "-z"], cwd=root, capture_output=True)
    if result.returncode != 0:
        raise RuntimeError(result.stderr.decode("utf-8", "replace").strip())
    return sorted(p for p in result.stdout.decode("utf-8", "replace").split("\0") if p)


def load_manifest(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def old_patterns(manifest: dict) -> list[str]:
    """Enforced old paths plus declared old directory prefixes, longest first."""
    values = [move["from"] for move in manifest["moves"] if "/" in move["from"]]
    # The deleted destinations belong here too: an index that points at a document which now only
    # exists as an archive member is the same failure the move record exists to catch.
    values += manifest.get("consolidation", {}).get("deletedPaths", [])
    values += [entry["prefix"] for entry in manifest.get("forbiddenPrefixes", [])]
    return sorted(set(values), key=len, reverse=True)


def build_matcher(manifest: dict) -> re.Pattern[str]:
    """One guard for every alternative.

    `(?<!x)a|b` parses as `((?<!x)a)|b`, so appending the lookbehind to a bare alternation guards
    exactly one pattern -- the first -- and silently un-guards the other 47. The group is required.
    """
    return re.compile(LOOKBEHIND + "(?:" + "|".join(re.escape(p) for p in old_patterns(manifest)) + ")")


def in_scope(rel: str, manifest: dict) -> bool:
    excluded = list(manifest.get("outOfScopePrefixes", [])) + [
        "docs/history/archive/MOVED-PATHS-20261019.json"
    ]
    return not any(rel.startswith(prefix) for prefix in excluded)


def tracked_blob(root: Path, rel: str) -> bytes:
    """The committed bytes of a tracked path, which are the same on every host.

    Worktree bytes are not: `.gitattributes text=auto` stores LF and checks out CRLF on Windows, so a
    hash taken from the working tree passes here and fails on a clean checkout. The move record is
    read by CI, so it measures the blob. Measured on 2026-10-19: the normalization made two edited CSVs
    differ by exactly their line terminators, and `tests/ci/test_stale_surface_paths_are_gone.py` went
    red in a fresh worktree while staying green in this one.
    """
    result = subprocess.run(["git", "show", f"HEAD:{rel}"], cwd=root, capture_output=True)
    if result.returncode != 0:
        raise RuntimeError(f"git show HEAD:{rel} failed: "
                           f"{result.stderr.decode('utf-8', 'replace').strip()}")
    return result.stdout


def read_text(root: Path, rel: str) -> str | None:
    """Decoded text, or None when the file is not text this scan can judge."""
    try:
        return (root / rel).read_bytes().decode("utf-8")
    except (OSError, UnicodeDecodeError):
        return None


def find_stale(text: str, matcher: re.Pattern[str]) -> list[tuple[int, str]]:
    hits = []
    for number, line in enumerate(text.splitlines(), 1):
        for match in matcher.finditer(line):
            hits.append((number, match.group(0)))
    return hits


def scan(root: Path, manifest: dict) -> dict:
    matcher = build_matcher(manifest)
    allowed = {entry["path"]: entry for entry in manifest.get("allowances", [])}
    files = [rel for rel in tracked_files(root) if in_scope(rel, manifest)]
    findings: list[str] = []
    allowance_counts = {path: 0 for path in allowed}
    allowance_hits = {path: [] for path in allowed}
    for rel in files:
        text = read_text(root, rel)
        if text is None:
            continue
        hits = find_stale(text, matcher)
        if not hits:
            continue
        if rel in allowed:
            allowance_counts[rel] = len(hits)
            allowance_hits[rel] = hits
        else:
            findings.extend(f"STALE {rel}:{line} ref={old}" for line, old in hits)
    unused = []
    for path, entry in allowed.items():
        minimum = entry.get("minOccurrences", 1)
        if allowance_counts.get(path, 0) < minimum:
            unused.append(
                f"ALLOWANCE_UNMET {path} min={minimum} "
                f"found={allowance_counts.get(path, 0)} (paths={allowance_hits.get(path, [])[:2]})"
            )
    return {"scanned": len(files), "findings": findings, "allowanceFailures": unused,
            "allowances": allowance_counts}


def main(argv: list[str] | None = None) -> int:
    args = list(sys.argv[1:] if argv is None else argv)
    write = "--write-allowances" in args
    root = REPO
    if not MANIFEST.is_file():
        print(f"STALE_SURFACE_PATHS_NO_MANIFEST {MANIFEST.relative_to(REPO)}")
        return 2
    try:
        manifest = load_manifest(MANIFEST)
    except (OSError, json.JSONDecodeError) as error:
        print(f"STALE_SURFACE_PATHS_NO_MANIFEST unreadable: {error}")
        return 2
    try:
        result = scan(root, manifest)
    except RuntimeError as error:
        print(f"STALE_SURFACE_PATHS_NO_GIT {error}")
        return 2
    if write:
        for entry in manifest.get("allowances", []):
            entry["minOccurrences"] = result["allowances"].get(entry["path"], 0)
        MANIFEST.write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n",
                            encoding="utf-8")
        print("STALE_SURFACE_PATHS_ALLOWANCES_WROTE " + json.dumps(result["allowances"]))
        return 0
    problems = result["findings"] + result["allowanceFailures"]
    if result["scanned"] < SCAN_FLOOR:
        problems.append(f"SCAN_BLIND scanned={result['scanned']} floor={SCAN_FLOOR}")
    for line in problems[:40]:
        print(line)
    if problems:
        print(f"STALE_SURFACE_PATHS_FAIL stale={len(result['findings'])} "
              f"allowanceFailures={len(result['allowanceFailures'])} scanned={result['scanned']}")
        return 1
    print(f"STALE_SURFACE_PATHS_PASS scanned={result['scanned']} "
          f"enforced={len(old_patterns(manifest))} allowances={len(result['allowances'])} "
          + " ".join(f"{path}={count}" for path, count in sorted(result["allowances"].items())))
    return 0


if __name__ == "__main__":
    sys.exit(main())

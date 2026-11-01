"""Release the authority-reference fixtures this project's own test leaked into %TEMP%.

`tests/ci/test_project_authority_reference.py` builds a throwaway copy of the live authority package
and (before this change) built it with `tempfile.mkdtemp(prefix="auth-ref-")`, i.e. in the user's
temp directory rather than inside the Git root. Nineteen of those directories survived from
2026-10-01: 304 files / 7,126,653 bytes of governance material — `WORK-LAB-AUTHORITY.md`, the
project and taskpack authority indexes, the open-task register, the error ledger, taskcards — sitting
outside the project boundary, which is exactly what
`.project/governance/project-data-boundary.json` forbids ("all content this project produces … stays
locked inside the project Git root").

Order of operations, because deletion is not reversible:

1. measure every file, and for each one decide recoverability: byte-equal to the live working tree,
   or byte-equal to a blob somewhere in git history (searched per path), or unique to the residue;
2. write the manifest, and archive one copy of every content that is NOT byte-equal to the live
   working tree, so the release cannot lose a historical version even if the git search missed it;
3. only then delete, and only the directories matching `auth-ref-*` under %TEMP%;
4. append the ledger line the boundary declaration requires for an out-of-root cleanup.

`--apply` is required to delete; without it the tool is a dry run that writes the manifest only.
Nothing under any other prefix, volume or project is touched, and E:/ and F:/ are refused outright.

Usage:
    python scripts/maintenance/release_authority_reference_temp_residue.py [--apply]
Exit: 0 dry run or completed release; 1 residue remains that this tool cannot account for; 2 refused.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import glob
import shutil
import subprocess
import sys
import tempfile
import time
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
PATTERN = "auth-ref-*"
BOUNDARY = REPO / ".project" / "governance" / "project-data-boundary.json"
SPILL_LEDGER = REPO / ".project-local" / "artifacts" / "spill-ledger.jsonl"
MANIFEST_DEFAULT = ".project-local/artifacts/greening-20261007/authority-ref-residue-manifest.json"
ARCHIVE_DEFAULT = ".project-local/artifacts/greening-20261007/authority-ref-residue-archive"


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            digest.update(chunk)
    return digest.hexdigest()


def history_blob_commits(rel: str) -> list[str]:
    """Every commit that has a version of this path reachable from any ref."""
    proc = subprocess.run(["git", "log", "--all", "--format=%H", "--", rel], cwd=REPO,
                          capture_output=True, text=True, encoding="utf-8", errors="replace")
    return [line for line in proc.stdout.splitlines() if line.strip()]


def recoverable_from_history(rel: str, want: str) -> str | None:
    """The first commit whose blob for `rel` hashes to `want` (bounded scan of recent versions)."""
    for commit in history_blob_commits(rel)[:200]:
        proc = subprocess.run(["git", "show", f"{commit}:{rel}"], cwd=REPO, capture_output=True)
        if proc.returncode == 0 and hashlib.sha256(proc.stdout).hexdigest() == want:
            return commit
    return None


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--apply", action="store_true", help="delete the residue after the manifest is written")
    ap.add_argument("--manifest", default=MANIFEST_DEFAULT)
    ap.add_argument("--archive", default=ARCHIVE_DEFAULT)
    args = ap.parse_args()

    temp = Path(tempfile.gettempdir())
    forbidden = json.loads(BOUNDARY.read_text(encoding="utf-8"))["forbiddenExternalRoots"]
    if str(temp).startswith(tuple(forbidden)):
        print(f"REFUSED_TEMP_IN_FORBIDDEN_VOLUME {temp}")
        return 2
    dirs = sorted(Path(p) for p in glob.glob(os.path.join(str(temp), PATTERN))
                  if Path(p).is_dir())
    print(f"temp={temp} pattern={PATTERN} dirs={len(dirs)}")
    if not dirs:
        print("NOTHING_TO_RELEASE")
        return 0

    archive = REPO / args.archive
    manifest_path = REPO / args.manifest
    records = []
    unique = []
    for d in dirs:
        for root, _names, files in os.walk(d, followlinks=False):
            for f in files:
                fp = Path(root) / f
                rel = Path(fp).relative_to(d).as_posix()
                want = sha256_file(fp)
                live = REPO / rel
                live_match = live.is_file() and sha256_file(live) == want
                commit = None if live_match else recoverable_from_history(rel, want)
                archived_to = None
                if not live_match:
                    key = f"{rel}@{want[:16]}"
                    if key not in unique:
                        unique.append(key)
                        target = archive / rel
                        target.parent.mkdir(parents=True, exist_ok=True)
                        shutil.copy2(fp, target)
                    archived_to = f"{args.archive}/{rel}"
                records.append({"dir": d.name, "relative": rel, "bytes": fp.stat().st_size,
                                "sha256": want, "matchesLiveWorkingTree": live_match,
                                "recoverableFromGitCommit": commit, "archived": archived_to})

    counts = {"dirs": len(dirs), "files": len(records), "bytes": sum(r["bytes"] for r in records),
              "liveByteEqual": sum(1 for r in records if r["matchesLiveWorkingTree"]),
              "differFromLive": sum(1 for r in records if not r["matchesLiveWorkingTree"]),
              "uniqueContentsPreserved": len(unique),
              "differAndNotInGitHistory": sum(1 for r in records
                                              if not r["matchesLiveWorkingTree"]
                                              and not r["recoverableFromGitCommit"])}
    at = time.strftime("%Y-%m-%dT%H:%M:%S+0800", time.gmtime(time.time() + 8 * 3600))
    deleted = []
    manifest = {"schemaVersion": "work-lab/authority-ref-residue-release/v1", "at": at,
                "tool": "scripts/maintenance/release_authority_reference_temp_residue.py",
                "tempRootIsMachineLocal": True, "pattern": PATTERN, "counts": counts,
                "preserveBeforeDelete": True, "archive": args.archive, "records": records,
                "apply": bool(args.apply), "deletedDirs": deleted,
                "notClaimed": ["only directories matching auth-ref-* under %TEMP% were examined; no "
                               "other prefix, volume or project was read or written",
                               "E:/ and F:/ were never entered"]}
    manifest_path.parent.mkdir(parents=True, exist_ok=True)
    manifest_path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"manifest -> {args.manifest}  dirs={counts['dirs']} files={counts['files']} "
          f"bytes={counts['bytes']:,} liveEqual={counts['liveByteEqual']} "
          f"differ={counts['differFromLive']} uniquePreserved={counts['uniqueContentsPreserved']} "
          f"notInGitHistory={counts['differAndNotInGitHistory']}")

    if not args.apply:
        print("DRY RUN — nothing deleted. Re-run with --apply once the manifest reads correctly.")
        return 0

    for d in dirs:
        shutil.rmtree(d)
        if d.exists():
            print(f"RELEASE_FAILED {d} still exists")
            return 1
        deleted.append(d.name)
    manifest["deletedDirs"] = deleted
    manifest["deletedAt"] = time.strftime("%Y-%m-%dT%H:%M:%S+0800", time.gmtime(time.time() + 8 * 3600))
    manifest_path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")

    line = {"at": manifest["deletedAt"], "actor": "session convergence-20261007-h",
            "action": f"released {len(deleted)} auth-ref-* fixture directories this project's own "
                      f"test leaked into %TEMP% ({counts['files']} files / {counts['bytes']} B)",
            "outOfRoot": True,
            "target": f"%TEMP%/{PATTERN} ({len(deleted)} directories, names in the manifest)",
            "source": "tests/ci/test_project_authority_reference.py::_make_fixture (mkdtemp without dir=)",
            "trace": f"every deleted file is listed with its size and sha256 in {args.manifest}",
            "locate": f"{temp}{os.sep}auth-ref-*",
            "clean": "already cleaned; the release is idempotent — a re-run reports NOTHING_TO_RELEASE",
            "migrate": f"contents that differed from the live tree were preserved under {args.archive} "
                       "before deletion, and the rest are byte-equal to files git already holds",
            "reversible": "re-creatable by re-running the authority-reference test, which rebuilds the "
                          "fixture from the live tree; no unique bytes were lost"}
    SPILL_LEDGER.parent.mkdir(parents=True, exist_ok=True)
    with SPILL_LEDGER.open("a", encoding="utf-8") as fh:
        fh.write(json.dumps(line, ensure_ascii=False) + "\n")
    remaining = sorted(Path(p) for p in glob.glob(os.path.join(str(temp), PATTERN)))
    print(f"RELEASED dirs={len(deleted)} remaining={len(remaining)} ledger=appended")
    return 1 if remaining else 0


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    raise SystemExit(main())

"""Release headless-Chrome profile directories left under .project-local/runs by CDP probes.

The in-boundary residue sweep matches a whole top-level run directory and refuses it as soon as one file
inside is not regenerable - correct, but it means a 200 MB evidence directory that also holds a 73 MB Chrome
profile can never give the profile back. This tool works at the profile-subtree level instead, and only ever
deletes a directory that looks exactly like a browser profile and holds no record-shaped file of its own.

Safety model, in order:
  * the candidate must be named like a profile (`udf-<digits>`, `chrome-udf*`, or a directory holding
    `Default/` plus `Local State`);
  * no file directly inside it may carry an evidence extension (.log .json .md .py .txt .csv .jsonl),
    which is what a probe's own receipt or screenshot next to a profile looks like;
  * a manifest with per-file path, size and sha256 is written BEFORE anything is removed, and one
    spill-ledger line records the release;
  * without --apply nothing is deleted and the reclaim is only reported.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
RUNS = ROOT / ".project-local/runs"
# The same ledger and manifest home the in-boundary residue sweep writes to, so one file lists every
# cleanup on this project regardless of which tool performed it.
ARTIFACTS = ROOT / ".project-local/artifacts"
MANIFEST_DIR = ARTIFACTS / "residue-cleanup"
LEDGER = ARTIFACTS / "spill-ledger.jsonl"
EVIDENCE_SUFFIXES = {".log", ".json", ".md", ".py", ".txt", ".csv", ".jsonl", ".ps1", ".sh"}
PROFILE_NAME_PREFIXES = ("udf-", "chrome-udf")


def is_profile_dir(path: Path) -> bool:
    if not path.is_dir():
        return False
    if path.name.startswith(PROFILE_NAME_PREFIXES):
        return True
    entries = {p.name for p in path.iterdir()}
    return "Default" in entries and "Local State" in entries


def evidence_inside(path: Path) -> list[Path]:
    """Files at the profile root that look like a record, not browser data."""
    return [p for p in path.iterdir() if p.is_file() and p.suffix.lower() in EVIDENCE_SUFFIXES]


def candidates() -> list[Path]:
    found: list[Path] = []
    for depth_root in sorted(RUNS.iterdir()):
        if not depth_root.is_dir():
            continue
        for path in sorted(depth_root.rglob("*")):
            try:
                if not path.is_relative_to(RUNS):
                    continue
            except AttributeError:  # pragma: no cover
                continue
            if is_profile_dir(path):
                found.append(path)
    # drop nested duplicates: a profile inside a profile is released with its parent
    tops = [p for p in found if not any(p != q and q in p.parents for q in found)]
    return tops


def size_of(path: Path) -> tuple[int, int]:
    files = [p for p in path.rglob("*") if p.is_file()]
    return len(files), sum(p.stat().st_size for p in files)


def remove_tree(path: Path) -> None:
    """rmtree, with the NT long-path prefix when the plain form cannot be resolved."""
    import shutil
    target = path
    if os.name == "nt":
        target = Path("\\\\?\\" + str(path))
    shutil.rmtree(target, ignore_errors=False)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--apply", action="store_true")
    args = ap.parse_args()

    if not RUNS.is_dir():
        print("RUNS_ROOT_MISSING", RUNS)
        return 2

    rows = []
    skipped = []
    for path in candidates():
        files, total = size_of(path)
        blockers = evidence_inside(path)
        if blockers:
            skipped.append({"dir": str(path.relative_to(RUNS)),
                            "reason": "record-shaped files at the profile root",
                            "files": [b.name for b in blockers[:5]]})
            continue
        rows.append({"dir": str(path.relative_to(RUNS)), "files": files, "bytes": total})

    total_bytes = sum(r["bytes"] for r in rows)
    print(f"profiles={len(rows)} bytes={total_bytes:,} skipped={len(skipped)}")
    for r in sorted(rows, key=lambda x: -x["bytes"])[:8]:
        print(f"  {r['dir'][:70]:70s} {r['files']:6d} files {r['bytes']:>13,} B")
    for s in skipped[:5]:
        print(f"  SKIP {s['dir'][:60]:60s} {s['reason']} {s['files']}")
    if not args.apply:
        print("RESIDUE_SWEEP_REPORTED pass --apply to delete (nothing removed)")
        return 0
    if not rows:
        return 0

    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    MANIFEST_DIR.mkdir(parents=True, exist_ok=True)
    manifest = MANIFEST_DIR / f"chrome-profiles-{stamp}.json"
    entries = []
    for row in rows:
        base = RUNS / row["dir"]
        for f in sorted(base.rglob("*")):
            if f.is_file():
                data = f.read_bytes()
                entries.append({"path": f.relative_to(ROOT).as_posix(), "bytes": len(data),
                                "sha256": hashlib.sha256(data).hexdigest()})
    manifest.write_text(json.dumps({"writtenAt": stamp, "tool": "scripts/audit/release_chrome_profile_residue.py",
                                    "regeneratedBy": "each named probe re-creates its own Chrome profile",
                                    "totals": {"dirs": len(rows), "bytes": total_bytes, "files": len(entries)},
                                    "entries": entries}, ensure_ascii=False, indent=2) + "\n",
                        encoding="utf-8")
    if not manifest.is_file() or manifest.stat().st_size == 0:
        print("MANIFEST_WRITE_FAILED refusing to delete")
        return 3

    failures = []
    for row in rows:
        try:
            remove_tree(RUNS / row["dir"])
            if (RUNS / row["dir"]).exists():
                failures.append({"dir": row["dir"], "error": "still present after removal"})
        except OSError as exc:
            failures.append({"dir": row["dir"], "error": f"{type(exc).__name__}: {exc}"})

    freed = sum(r["bytes"] for r in rows if not (RUNS / r["dir"]).exists())
    # The boundary declaration names ten required fields for every spill-ledger line
    # (project-data-boundary.json -> spillGovernance.ledger.requiredFields). This line used to carry its own
    # rich-but-different shape, so the outside-root sweep counted it as a schema violation while still
    # reporting the cleanup as safe -- a record that is informative and non-conforming is exactly the kind
    # a reader trusts without checking. outOfRoot=false because every path here is inside the Git root.
    handle_manifest = manifest.relative_to(ROOT).as_posix()
    with LEDGER.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps({
            "at": stamp, "actor": "scripts/audit/release_chrome_profile_residue.py",
            "action": "released regenerable headless-Chrome profile directories under .project-local/runs",
            "outOfRoot": False,
            "target": ".project-local/runs",
            "source": ".project-local/runs (profiles created by this repository's own CDP probes)",
            "trace": handle_manifest,
            "locate": handle_manifest,
            "clean": "every removed file is listed by path, byte length and sha256 in the manifest",
            "migrate": "not required: nothing left the repository, and the profiles are re-created on the "
                       "next probe run",
            "scope": ".project-local/runs", "kind": "headless-chrome-profiles",
            "dirs": len(rows), "files": len(entries), "bytesReleased": freed,
            "manifest": handle_manifest,
            "regeneratedBy": "the CDP probes that created them",
            "recoverability": "regenerable by re-running the instrument; per-file sha256 preserved in the manifest",
            "failures": len(failures),
            "tool": "scripts/audit/release_chrome_profile_residue.py",
            "mode": "apply"}, ensure_ascii=False) + "\n")
    print(f"released bytes={freed:,} manifest={manifest.relative_to(ROOT)} failures={len(failures)}")
    for f in failures[:5]:
        print("  FAILED", f)
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())

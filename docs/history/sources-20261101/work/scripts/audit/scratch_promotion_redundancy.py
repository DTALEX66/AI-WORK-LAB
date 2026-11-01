"""Release scratch originals only where a tracked copy is byte-identical.

Round F promoted probe scripts out of `.project-local/runs/<session>/` into `scripts/audit/` and
`scripts/maintenance/`, and deliberately left the scratch originals on disk. They are redundant only
if the tracked copy is the same bytes — if I edited one after promoting it, the scratch file is the
only copy of the other version, and deleting it would destroy a divergence rather than clean up.

So this compares sha256 per basename pair and classifies:
  REDUNDANT      identical bytes  -> releasable with `--apply`
  DIVERGENT      different bytes  -> kept, and reported, because neither copy is the other
  UNPAIRED       scratch file with no tracked namesake -> kept (it may be cited as history)

Usage: python scripts/audit/scratch_promotion_redundancy.py [--apply] [--json PATH]
Exit: 0 always in report mode; 1 if --apply found nothing releasable.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
import sys
import time
from pathlib import Path, PurePosixPath

REPO = Path(__file__).resolve().parents[2]
# Only run scratch is eligible. `.project-local/artifacts/` is the evidence root AGENTS.md tells
# rounds to preserve, and byte-identical does not make a preserved copy worthless — a rescue staging
# area exists precisely so that content is reachable from a second location.
SCRATCH_ROOTS = (".project-local/runs/",)
TRACKED_PREFIXES = ("scripts/audit/", "scripts/maintenance/", "tests/workflow-assistance/")


def sha256(p: Path) -> str:
    h = hashlib.sha256()
    with p.open("rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 24), b""):
            h.update(chunk)
    return h.hexdigest()


def tracked_by_name() -> dict[str, list[str]]:
    raw = subprocess.run(["git", "-c", "core.quotePath=false", "ls-files", "-z"],
                         cwd=REPO, capture_output=True).stdout.split(b"\0")
    out: dict[str, list[str]] = {}
    for rel in (p.decode("utf-8", "replace") for p in raw if p):
        if rel.startswith(TRACKED_PREFIXES):
            out.setdefault(PurePosixPath(rel).name, []).append(rel)
    return out


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--apply", action="store_true")
    ap.add_argument("--json", default=".project-local/runs/convergence-20261007-h/"
                                        "scratch_redundancy.json")
    args = ap.parse_args()

    by_name = tracked_by_name()
    rows = []
    for root in SCRATCH_ROOTS:
        base = REPO / root
        if not base.is_dir():
            continue
        for p in base.rglob("*"):
            if not p.is_file() or p.suffix not in {".py", ".mjs", ".sh"}:
                continue
            if "__pycache__" in p.parts or "ci-worktree" in p.parts:
                continue
            matches = by_name.get(p.name, [])
            if not matches:
                continue
            src = sha256(p)
            identical = [m for m in matches if sha256(REPO / m) == src]
            rows.append({
                "scratch": p.relative_to(REPO).as_posix(),
                "bytes": p.stat().st_size,
                "sha256": src,
                "tracked": matches,
                "identicalTo": identical,
                "state": "REDUNDANT" if identical else "DIVERGENT",
            })

    redundant = [r for r in rows if r["state"] == "REDUNDANT"]
    freed = 0
    deleted = []
    if args.apply:
        for r in redundant:
            target = REPO / r["scratch"]
            before = sha256(target)
            assert before == r["sha256"], r["scratch"]
            assert all((REPO / m).is_file() and sha256(REPO / m) == before for m in r["identicalTo"])
            target.unlink()
            assert not target.exists(), r["scratch"]
            freed += r["bytes"]
            deleted.append(r["scratch"])
        redundant = [r for r in redundant if r["scratch"] not in deleted]

    doc = {"schemaVersion": "work-lab/scratch-promotion-redundancy/v1",
           "at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
           "tool": "scripts/audit/scratch_promotion_redundancy.py",
           "rule": ("a scratch original is released only when a tracked copy has the identical "
                    "sha256; a divergent copy is kept because neither version contains the other"),
           "counts": {"pairedScratchFiles": len(rows),
                      "redundantRemaining": len(redundant),
                      "divergent": sum(1 for r in rows if r["state"] == "DIVERGENT"),
                      "deletedThisRun": len(deleted), "bytesFreedThisRun": freed},
           "deletedThisRun": deleted,
           "redundantRemaining": [{"scratch": r["scratch"], "bytes": r["bytes"],
                                   "identicalTo": r["identicalTo"]} for r in redundant],
           "divergentRows": [{"scratch": r["scratch"], "tracked": r["tracked"],
                              "scratchSha": r["sha256"],
                              "trackedSha": [sha256(REPO / m) for m in r["tracked"]]}
                             for r in rows if r["state"] == "DIVERGENT"]}
    out = REPO / args.json
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(doc, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"paired={doc['counts']['pairedScratchFiles']} redundant_remaining={len(redundant)} "
          f"divergent={doc['counts']['divergent']} deleted={len(deleted)} freed={freed:,} B")
    for d in deleted[:10]:
        print(f"  RELEASED {d}")
    for r in doc["divergentRows"][:10]:
        print(f"  DIVERGENT {r['scratch']}  vs {r['tracked']}")
    print(f"report -> {args.json}")
    return 0 if (deleted or not args.apply) else 1


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    raise SystemExit(main())

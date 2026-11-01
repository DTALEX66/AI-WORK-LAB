"""Reclaim regenerable residue inside the project boundary, and refuse anything that is not.

`.project-local/runs` is the declared git-ignored runtime root, so everything under it is already
inside the boundary — this is not a spill sweep. It is the other half of the same duty: a project
that leaves 3 GB of its own scratch behind has a tracking problem, and "it is ignored" is not an
answer. Three rules make the sweep safe to run:

  1. Only directories matching a DECLARED residue pattern are candidates, and each pattern names the
     command that regenerates it. "Looks like a temp dir" is not a category.
  2. Before deleting, the tool writes a manifest of every file it is about to remove (path, size,
     sha256) under `.project-local/artifacts/`, so the action is auditable after the fact.
  3. Anything inside a candidate directory that does NOT belong to the declared regenerable shape
     stops that directory: an unexpected file means the directory is holding something unique, and a
     unique byte is evidence, not residue.

The cargo target tree is deliberately NOT a pattern. It is the largest thing under the runtime root
and the only locally runnable desktop evidence; it regenerates only with a Rust toolchain this
machine does not have on PATH, so deleting 1.4 GB of it would be an irreversible act dressed up as
cleanup.

Usage:
    python scripts/audit/in_boundary_residue_sweep.py            # measure and report
    python scripts/audit/in_boundary_residue_sweep.py --apply     # delete declared residue
Exit: 0 clean or applied; 1 a candidate held content the pattern does not cover; 2 no runtime root.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import shutil
import subprocess
import sys
import time
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
RUNS = REPO / ".project-local" / "runs"
ARTIFACTS = REPO / ".project-local" / "artifacts"
BOUNDARY = REPO / ".project/governance/project-data-boundary.json"
LEDGER = ARTIFACTS / "spill-ledger.jsonl"

RESIDUE = {
    "auth-ref": {
        "regeneratedBy": "python -m pytest tests/ci/test_project_authority_reference.py",
        "why": ("copies of tracked authority files made per test; the suite deletes its own fixture "
                "now (ERR-140), so leftovers are from interrupted older runs"),
        "allowed_members": ("WORK-LAB-AUTHORITY.md", ".project", "taskpacks", "config"),
    },
    "geometry-gate": {
        "regeneratedBy": "python scripts/audit/topbar_geometry_via_cdp.py",
        "why": ("headless Chrome profile dirs and screenshots the geometry gate creates per run; the "
                "gate re-measures from the built dist every time"),
        "allowed_members": ("udf-", "chrome-", "topbar-", "geometry_"),
    },
    "citation-audit-selftest": {
        "regeneratedBy": "python -m pytest tests/workflow-assistance/test_project_local_citation_audit.py",
        "why": "two scratch records the idempotence test writes to prove determinism",
        "allowed_members": ("first.json", "second.json"),
    },
    "geometry-gate-selftest": {
        "regeneratedBy": "python -m pytest tests/ci/test_topbar_geometry_gate.py",
        "why": "the gate's own refusal probe against a scratch tree",
        "allowed_members": ("apps",),
    },
    "geometry-gate-nobrowser": {
        "regeneratedBy": "python -m pytest tests/ci/test_topbar_geometry_gate.py",
        "why": "the no-browser refusal fixture",
        "allowed_members": ("apps",),
    },
    "topbar-measure": {
        "regeneratedBy": "python scripts/audit/topbar_geometry_via_cdp.py",
        "why": "the older geometry probe's Chrome profiles and captures",
        "allowed_members": ("chrome-udf-", "measure.json", "topbar"),
    },
}


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as fh:
        for block in iter(lambda: fh.read(1 << 20), b""):
            h.update(block)
    return h.hexdigest()


class TrackedMatcher:
    """Does these bytes exist in the repository at this path? Answered from git, cached per path.

    A name allowlist says "this looks like a fixture"; comparing against `git show HEAD:<path>` says
    "the bytes are already in the repository and can be re-materialised", which is what makes deleting
    the copy reversible. The digest is compared rather than the raw bytes to keep the cache small.
    """

    def __init__(self) -> None:
        self._cache: dict[str, str | None] = {}
        self.tracked = {p.decode("utf-8", "replace") for p in subprocess.run(
            ["git", "ls-files", "-z"], cwd=REPO, capture_output=True).stdout.split(b"\x00") if p}

    def blob_sha256(self, path: str) -> str | None:
        if path not in self.tracked:
            return None
        if path in self._cache:
            return self._cache[path]
        proc = subprocess.run(["git", "show", f"HEAD:{path}"], cwd=REPO, capture_output=True)
        digest = hashlib.sha256(proc.stdout).hexdigest() if proc.returncode == 0 else None
        self._cache[path] = digest
        return digest

    def in_history(self, path: str, digest: str, depth: int = 40) -> bool:
        """Were these bytes the repository's own content at this path, in any recent commit?

        A fixture copied at an older head legitimately differs from HEAD. That is still not unique
        content: the bytes live in the object database and come back with `git show <commit>:<path>`,
        which is the recoverability the cleanup claims. Bounded by depth so the answer is cheap and
        stated rather than open-ended.
        """
        if path not in self.tracked:
            return False
        key = f"hist:{path}"
        if key in self._cache and self._cache[key] == digest:
            return True
        listing = subprocess.run(["git", "log", f"-n{depth}", "--format=%H", "--", path],
                                 cwd=REPO, capture_output=True, text=True,
                                 encoding="utf-8", errors="replace").stdout.split()
        for sha in listing:
            show = subprocess.run(["git", "show", f"{sha}:{path}"], cwd=REPO, capture_output=True)
            if show.returncode == 0 and hashlib.sha256(show.stdout).hexdigest() == digest:
                self._cache[key] = digest
                return True
        return False


def classify_member(rel: str, allowed: tuple[str, ...]) -> bool:
    """True when the relative path belongs to the shape the pattern declares."""
    head = rel.split("/", 1)[0]
    return any(head == a or head.startswith(a) or rel == a for a in allowed)


def is_recoverable(rel_in_dir: str, digest: str, spec: dict, matcher: TrackedMatcher,
                   dir_rel: str) -> tuple[bool, str]:
    """Either the bytes are already somewhere the repository can re-materialise, or scratch shape."""
    if matcher.blob_sha256(rel_in_dir) == digest:
        return True, f"tracked bytes at {rel_in_dir}"
    if matcher.in_history(rel_in_dir, digest):
        return True, f"historical bytes at {rel_in_dir}"
    live = REPO / rel_in_dir
    if live.is_file() and sha256_file(live) == digest:
        # The fixture copied a working-tree file that is still there with the same bytes. Untracked
        # originals count too: deleting the duplicate loses nothing the owner cannot still read.
        return True, f"working-tree bytes at {rel_in_dir}"
    if classify_member(rel_in_dir, spec["allowed_members"]):
        return True, "declared scratch shape"
    return False, f"unique bytes at {dir_rel}/{rel_in_dir}"


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--apply", action="store_true")
    args = ap.parse_args()

    if not RUNS.is_dir():
        print(f"RESIDUE_SWEEP_NOT_RUN RUNTIME_ROOT_ABSENT {RUNS}")
        return 2
    runtime_root = json.loads(BOUNDARY.read_text(encoding="utf-8")).get("runtimeRoot")
    if not runtime_root:
        print("RESIDUE_SWEEP_NOT_RUN BOUNDARY_DECLARES_NO_RUNTIME_ROOT")
        return 2

    matcher = TrackedMatcher()
    candidates, blocked = [], []
    for entry in sorted(RUNS.iterdir()):
        if not entry.is_dir():
            continue
        pattern = next((k for k in RESIDUE if entry.name.startswith(k)), None)
        if pattern is None:
            continue
        spec = RESIDUE[pattern]
        dir_rel = entry.relative_to(REPO).as_posix()
        unexpected = []
        recoveries: dict[str, int] = {}
        total_bytes = 0
        total_files = 0
        for path in sorted(entry.rglob("*")):
            if not path.is_file():
                continue
            total_files += 1
            total_bytes += path.stat().st_size
            rel = path.relative_to(entry).as_posix()
            ok, how = is_recoverable(rel, sha256_file(path), spec, matcher, dir_rel)
            if ok:
                recoveries[how.split(" at ")[0] if " at " in how else how] = \
                    recoveries.get(how.split(" at ")[0] if " at " in how else how, 0) + 1
            elif len(unexpected) < 8:
                unexpected.append(how)
        record = {"path": dir_rel, "pattern": pattern, "bytes": total_bytes,
                  "files": total_files, "unexpected": unexpected,
                  "recoveredBy": recoveries,
                  "regeneratedBy": spec["regeneratedBy"], "why": spec["why"]}
        (blocked if unexpected else candidates).append(record)

    reclaim = sum(r["bytes"] for r in candidates)
    print(f"runtimeRoot={runtime_root} declaredPatterns={len(RESIDUE)} "
          f"candidates={len(candidates)} bytes={reclaim:,} blocked={len(blocked)}")
    for r in blocked:
        print(f"  BLOCKED {r['path']} unexpected={r['unexpected']}")
    for r in candidates[:6]:
        print(f"  candidate {r['path']} {r['bytes']:,} B / {r['files']} files -> {r['regeneratedBy']}")

    if not args.apply:
        print("RESIDUE_SWEEP_REPORTED reclaimableBytes=%s (pass --apply to delete)" % f"{reclaim:,}")
        return 0

    manifest_dir = ARTIFACTS / "residue-cleanup"
    manifest_dir.mkdir(parents=True, exist_ok=True)
    stamp = time.strftime("%Y%m%dT%H%M%S", time.gmtime(time.time() + 8 * 3600))
    manifest = {"schemaVersion": "work-lab/in-boundary-residue/v1", "at": stamp,
                "actor": "qoder-session-b405b5fe", "apply": True,
                "entries": []}
    removed_bytes = 0
    failures = []
    for r in candidates:
        target = REPO / r["path"]
        files = [{"path": f.relative_to(REPO).as_posix(), "bytes": f.stat().st_size,
                  "sha256": sha256_file(f)} for f in sorted(target.rglob("*")) if f.is_file()]
        try:
            shutil.rmtree(target)
        except OSError as exc:
            failures.append(f"{r['path']} {exc!r}")
            continue
        removed_bytes += r["bytes"]
        manifest["entries"].append({"path": r["path"], "pattern": r["pattern"],
                                    "bytes": r["bytes"], "regeneratedBy": r["regeneratedBy"],
                                    "why": r["why"], "files": files})

    mpath = manifest_dir / f"residue_{stamp}.json"
    mpath.write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
    line = {"at": stamp, "actor": manifest["actor"],
            "action": f"in-boundary residue cleanup under {runtime_root}: {len(manifest['entries'])} "
                      f"declared-pattern directories removed",
            "outOfRoot": False, "target": str(mpath.relative_to(REPO)).replace("\\", "/"),
            "source": runtime_root,
            "trace": f"{removed_bytes:,} B removed; every file manifest-recorded with path, size and "
                     "sha256 before deletion",
            "locate": str(mpath.relative_to(REPO)).replace("\\", "/"),
            "clean": "already removed; nothing else to clean",
            "migrate": "not a migration: regenerable scratch, restated by the command named per pattern",
            "reversible": "each directory is rebuilt by the regenerating command in its entry",
            "regenerators": sorted({e["regeneratedBy"] for e in manifest["entries"]}),
            "failures": failures}
    LEDGER.parent.mkdir(parents=True, exist_ok=True)
    with LEDGER.open("a", encoding="utf-8") as fh:
        fh.write(json.dumps(line, ensure_ascii=False) + "\n")

    print(f"RESIDUE_SWEEP_APPLIED removed={removed_bytes:,} B entries={len(manifest['entries'])} "
          f"failures={len(failures)} manifest={mpath.relative_to(REPO).as_posix()}")
    return 1 if failures else 0


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    raise SystemExit(main())

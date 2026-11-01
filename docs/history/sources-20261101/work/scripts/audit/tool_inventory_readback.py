"""Regenerate the full tracked-instrument inventory under scripts/audit and scripts/maintenance.

`docs/audits/PROBE_TOOL_PROMOTION_2026-10-07.json` was a promotion event record — 22 entries, each a
scratch original that became a tracked tool. It was never meant to describe the tree, and by the end of
round H the tree held 30 such files while the record listed 22: an inventory that only grows in prose
is the kind of record that misleads the next session into re-inventing a tool that already exists.

This produces the authoritative, complete inventory instead: path, sha256, bytes, lines, plus two
signals that say whether anything actually depends on the file —

  citedByLedgerPromises  tracked error-ledger `lifecycle.regressionCommand` strings naming it
  citedByRecords         any other tracked file (docs, audits, handoffs, registries) naming it

Usage: python scripts/audit/tool_inventory_readback.py [--out docs/audits/TOOL_INVENTORY_2026-10-07.json]

Ordering rule, learned the expensive way (ERR-151): this tool discovers instruments from the git
INDEX, so a newly added script is invisible to it until `git add` has run. Re-measure the inventory
AFTER staging and BEFORE committing — the 2026-10-07 head 1b2a747 was red on the runner for exactly
this reason (`tracked instruments absent from the inventory: ['scripts/audit/executor_live_probe.py']`)
while passing locally, because the committed inventory had been computed a moment earlier against a
file that was still untracked.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import re
import subprocess
import sys
import time
from pathlib import Path, PurePosixPath

REPO = Path(__file__).resolve().parents[2]
DIRS = ("scripts/audit/", "scripts/maintenance/")
DEFAULT_OUT = "docs/audits/TOOL_INVENTORY_2026-10-07.json"


def citation_sources(all_files: list[str], excluded: set[str]) -> list[str]:
    """The documents allowed to count as a citation of an instrument.

    The report names every instrument it carries, so letting it cite them makes the emission
    self-referential: a newly added tool reads as `unclaimed` on the first pass and as claimed on the
    second, which both prints a false warning and forces a second run before the file describes itself.
    Measured 2026-10-28 with a scratch instrument: the pre-fix generator changed 14 content lines between
    emission 1 and emission 2, the fixed one changes 0.

    Exclusion is by identity, not by output path: `tests/ci/test_shipped_projections_are_current.py`
    re-generates into a temporary file and compares that against the shipped report, so a rule keyed only
    on `--out` would have the fresh run count the shipped report as a citer and the two would never agree.
    """
    return [f for f in all_files if not f.startswith(DIRS) and f not in excluded]


def relative_to_repo(target: str) -> str:
    """`target` as a repo-relative posix path, whether the caller passed it relative or absolute."""
    path = Path(target)
    if not path.is_absolute():
        path = Path.cwd() / path
    try:
        return path.resolve().relative_to(REPO).as_posix()
    except ValueError:
        return path.as_posix()


def tracked_files() -> list[str]:
    raw = subprocess.run(["git", "-c", "core.quotePath=false", "ls-files", "-z"],
                         cwd=REPO, capture_output=True).stdout.split(b"\0")
    return [p.decode("utf-8", "replace") for p in raw if p]


def blob(rel: str) -> bytes | None:
    """The committed bytes of `rel`, or None when it is not in HEAD yet."""
    r = subprocess.run(["git", "show", f"HEAD:{rel}"], cwd=REPO, capture_output=True)
    return r.stdout if r.returncode == 0 else None


def staged(rel: str) -> bytes | None:
    """The bytes the next commit will carry, or None when the path is not in the index."""
    r = subprocess.run(["git", "show", f":{rel}"], cwd=REPO, capture_output=True)
    return r.stdout if r.returncode == 0 else None


def digest(rel: str) -> tuple[str, int, int, str]:
    """(sha256, bytes, lines, basis).

    The digest is of the git blob, not the working file: `.gitattributes` says `* text=auto`, so the
    same source has different bytes on a Windows checkout and on a Linux runner, and a digest recorded
    over working-tree bytes is what turned CI red at three heads (ERR-125). The index is read before HEAD
    because HEAD is the previous commit: measuring a modified instrument before committing it recorded the
    OLD blob, and the very next head was red on the runner for exactly that (ERR-153). A path that is in
    neither is hashed from the working tree and says so in its own basis field.
    """
    data, basis = staged(rel), "git-index"
    if data is None:
        data, basis = blob(rel), "git-blob-at-HEAD"
    if data is None:
        data = (REPO / rel).read_bytes()
        basis = "working-tree-uncommitted"
    lines = data.count(b"\n") + (0 if data.endswith(b"\n") or not data else 1)
    return hashlib.sha256(data).hexdigest(), len(data), lines, basis


def untracked_instruments(porcelain: str) -> list[str]:
    """The still-untracked instruments in `git status --porcelain` output.

    Only `??` qualifies. A staged-new file (`A `) is already in the index and `digest()` reads it from
    there; the first version warned about it too, which told a reader to stage a file they had just
    staged — a false directive from the guard that measures the guards (ERR-155).
    """
    out = []
    for line in porcelain.splitlines():
        if line.startswith("??"):
            path = line[3:].strip().replace("\\", "/")
            if path.endswith(".py") and path.startswith(DIRS):
                out.append(path)
    return out


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default=DEFAULT_OUT)
    args = ap.parse_args()

    all_files = tracked_files()
    tools = [f for f in all_files if f.startswith(DIRS)]

    # The discovery set comes from the index, so a *still-untracked* instrument is invisible until it is
    # staged. Saying so loudly here is what turns a future red-on-the-runner into a message at the
    # moment of the mistake (ERR-151).
    proc = subprocess.run(["git", "status", "--porcelain", "--untracked-files=normal", "--"] +
                          list(DIRS), cwd=REPO, capture_output=True, text=True,
                          encoding="utf-8", errors="replace")
    untracked = untracked_instruments(proc.stdout or "")
    if untracked:
        print(f"WARNING untracked instruments are not in the index yet, so the inventory cannot "
              f"describe them: {untracked}. Stage first, then re-measure.")

    if not tools:
        print("NO_TRACKED_TOOLS under " + ", ".join(DIRS))
        return 2

    # a promise is a `lifecycle.regressionCommand` string; read the parsed ledger, not raw lines
    promises: dict[str, int] = {}
    try:
        ledger = json.loads((REPO / "taskpacks/current/error-ledger.json").read_text(encoding="utf-8"))
        for err in ledger["errors"]:
            cmd = (err.get("lifecycle") or {}).get("regressionCommand") or ""
            for tool in tools:
                if PurePosixPath(tool).name in cmd:
                    promises[tool] = promises.get(tool, 0) + 1
    except (OSError, ValueError, KeyError) as exc:
        print(f"LEDGER_UNREAD {type(exc).__name__}: {exc}")

    # The report is the thing being written, so it cannot also be evidence about itself; `citation_sources`
    # says why. Writing it under an instrument root would hide a real subject behind that exclusion.
    out_rel = relative_to_repo(args.out)
    if out_rel.startswith(DIRS):
        print(f"INVENTORY_OUT_INSIDE_INSTRUMENT_ROOT refusing to exclude its own subject: {out_rel}")
        return 4
    others = citation_sources(all_files, {DEFAULT_OUT, out_rel})
    entries = []
    for tool in sorted(tools):
        sha, size, lines, basis = digest(tool)
        name = PurePosixPath(tool).name
        citing = [o for o in others if name in (REPO / o).read_text(encoding="utf-8",
                                                                    errors="replace")]
        entries.append({"path": tool, "sha256": sha, "bytes": size, "lines": lines,
                        "digestBasis": basis,
                        "citedByLedgerPromises": promises.get(tool, 0),
                        "citedByRecords": len(citing),
                        "citedBy": sorted(citing)[:6]})

    unclaimed = [e["path"] for e in entries if e["citedByLedgerPromises"] == 0
                 and e["citedByRecords"] == 0]
    doc = {
        "schemaVersion": "work-lab/tool-inventory/v1",
        "generatedAt": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "generatedBy": "scripts/audit/tool_inventory_readback.py",
        "scope": list(DIRS),
        "basis": "git ls-files at HEAD; each digest is the sha256 of the committed blob bytes "
                 "(`.gitattributes` sets `* text=auto`, so working-tree bytes differ per platform — "
                 "ERR-125), except files not yet in HEAD, which say so in their own digestBasis",
        "counts": {"trackedTools": len(entries),
                   "withLedgerPromise": sum(1 for e in entries if e["citedByLedgerPromises"]),
                   "referencedSomewhere": sum(1 for e in entries if e["citedByRecords"]),
                   "unclaimed": len(unclaimed)},
        "unclaimed": unclaimed,
        "relationToPromotionEvent": {
            "record": "docs/audits/PROBE_TOOL_PROMOTION_2026-10-07.json",
            "note": "that file is the 2026-10-07 promotion of 22 scratch originals and stays as "
                    "history; this one is the live inventory of all 30 tracked instruments and is the "
                    "file the coverage gate reads"},
        "tools": entries,
    }
    out = REPO / args.out
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_bytes(json.dumps(doc, ensure_ascii=False, indent=2).replace("\n", "\r\n").encode())
    back = json.loads(out.read_text(encoding="utf-8"))
    assert len(back["tools"]) == len(entries)
    print(f"trackedTools={len(entries)} withLedgerPromise={doc['counts']['withLedgerPromise']} "
          f"referencedSomewhere={doc['counts']['referencedSomewhere']} unclaimed={len(unclaimed)}")
    for p in unclaimed:
        print(f"  UNCLAIMED {p}")
    print(f"inventory -> {args.out} ({out.stat().st_size} bytes)")
    return 0


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    raise SystemExit(main())

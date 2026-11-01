#!/usr/bin/env python3
"""Generate a byte-checkable FROZEN manifest for a closed history surface.

Why this exists: DOCUMENT-CENSUS §7.3 asked for FROZEN declarations for the frozen surfaces, and the
repository already carries three archive conventions of which exactly one
(`reports/audit-archive/20260930/ARCHIVE-INDEX.json`) can be checked to the byte. A "frozen" claim that
nothing re-derives is a sentence, not a control: the census itself had already gone stale about one of
these directories (`90-archive/` is described as holding frozen reports and now contains one marker
file). So this emits the same field names the checkable convention uses — `path`, `bytes`, `sha256` —
and `tests/ci/test_frozen_surfaces_are_intact.py` re-derives and compares them on every gate run.

Determinism: entries are sorted by path and the payload carries no timestamp; the two git identities
that pin the snapshot (commit and tree) are recorded instead, because they are re-derivable on any
machine while a wall-clock string is not.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SCHEMA = "work-lab/frozen-surface-manifest/v1"
# The same keys ARCHIVE-INDEX.json already uses for a byte-checkable member, so a frozen surface and an
# audit archive are read with one mental model rather than two.
MEMBER_KEYS = ("path", "bytes", "sha256")


def git(*args: str) -> str:
    done = subprocess.run(["git", *args], cwd=ROOT, capture_output=True, text=True,
                          encoding="utf-8", errors="replace")
    return (done.stdout or "").strip()


def tracked_files(root: str) -> list[str]:
    out = git("ls-files", "-z", "--", root)
    if not out:
        return []
    # `-z` output is NUL-separated; splitting it any other way loses empty paths and mangles the
    # CJK names these trees are full of.
    return sorted(p for p in out.split("\0") if p.strip())


def git_bytes(*args: str) -> bytes | None:
    result = subprocess.run(["git", *args], cwd=ROOT, capture_output=True)
    return result.stdout if result.returncode == 0 else None


def sha256_of(rel: str) -> tuple[str, int]:
    """The COMMITTED bytes, never the checkout's.

    Measured on docs/history/archive/workflow-convergence-receipt-20261005.json: the Windows working tree
    holds CRLF (44 pairs, sha256 b8262a28dc4b...) while the object stores LF (0 pairs, sha256
    9646c7e452a3...) because `.gitattributes` says `* text=auto` and this box has core.autocrlf=true. A
    manifest built from disk therefore recorded a digest that a Linux runner can never reproduce -- which is
    how CI convicted a file nobody had touched. "Frozen" is a claim about what is in git, so the digest comes
    from the index (the bytes the next commit carries) and falls back to HEAD; in a CI checkout they are the
    same object.
    """
    for reference in (f":{rel}", f"HEAD:{rel}"):
        data = git_bytes("show", reference)
        if data is not None:
            return hashlib.sha256(data).hexdigest(), len(data)
    raise SystemExit(f"FROZEN_MANIFEST_FAIL no committed bytes for {rel}")


def build(root: str, manifest_name: str = "FROZEN-MANIFEST.json") -> dict:
    files = tracked_files(root)
    # A manifest cannot digest itself: the bytes it would hash include the file being written. It is
    # excluded by name, and the gate asserts that same exclusion, so the rule is visible rather than a
    # silent hole through which the manifest could be rewritten freely.
    manifest_path = f"{root.rstrip('/')}/{manifest_name}"
    files = [f for f in files if f.replace("\\", "/") != manifest_path]
    if not files:
        raise SystemExit(f"FROZEN_MANIFEST_REFUSED root={root} tracked_files=0 — a digest over no "
                         f"files is a plausible-looking value for the null case (sha256 of nothing is "
                         f"e3b0c442...), so an empty or already-drifted surface must never publish one")
    members: list[dict] = []
    absent: list[str] = []
    for rel in files:
        path = ROOT / rel
        if not path.is_file():
            absent.append(rel)
            continue
        digest, size = sha256_of(rel)
        members.append({"path": rel.replace("\\", "/"), "bytes": size, "sha256": digest})
    if absent:
        raise SystemExit(f"FROZEN_MANIFEST_REFUSED root={root} tracked_but_absent={len(absent)} "
                         f"first={absent[:3]} — a manifest over bytes that are not there is a lie "
                         f"about the working tree, not about the archive")
    total = sum(m["bytes"] for m in members)
    return {
        "schemaVersion": SCHEMA,
        "root": root,
        "normative": False,
        "generatedFromCommit": git("rev-parse", "HEAD"),
        "generatedFromTree": git("rev-parse", "HEAD^{tree}"),
        "totals": {"files": len(members), "bytes": total},
        "files": members,
    }


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--root", required=True, help="surface to freeze, repo-relative (e.g. knowledge-staging)")
    ap.add_argument("--out", required=True, help="manifest path, repo-relative")
    args = ap.parse_args(argv)

    doc = build(args.root)
    out = ROOT / args.out
    out.parent.mkdir(parents=True, exist_ok=True)
    # newline="" so the bytes written are exactly the bytes hashed minus the JSON itself; a
    # platform-dependent translation here would make the manifest disagree with its own next check.
    out.write_text(json.dumps(doc, indent=2, ensure_ascii=False) + "\n", encoding="utf-8", newline="")
    back = json.loads(out.read_text(encoding="utf-8"))
    if back["totals"] != doc["totals"] or len(back["files"]) != len(doc["files"]):
        print(f"FROZEN_MANIFEST_VERIFY_FAILED out={args.out}")
        return 1
    print(f"FROZEN_MANIFEST_OK root={doc['root']} files={doc['totals']['files']} "
          f"bytes={doc['totals']['bytes']} out={args.out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())

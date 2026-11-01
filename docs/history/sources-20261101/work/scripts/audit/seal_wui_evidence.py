#!/usr/bin/env python
"""Seal the WUI evidence directory against the bytes the front end is built from right now.

A render receipt is a claim about a bundle, not about a commit. On 2026-10-10 the Observer `dist` was
rebuilt (a production source change landed after the captures) and every screenshot, geometry, legibility,
DPI and keyboard receipt in `.project-local/artifacts/wui-20261009` silently became a description of bytes
that no longer existed. Nothing in the tree said so, and a reader had no way to tell "measured" from
"measured, then superseded".

This script makes the difference machine-visible: it walks the evidence set, reads the bundle identity each
receipt carries (`servedBundle.bundleDigest` from the CDP instruments, `distBundle.sha256` from the native
keyboard gate), and sorts every file BOUND / STALE / UNBOUND against the digest computed from `dist` right
now. A PNG has no self-describing bundle, so it is bound through the receipt that lists it.

The seal's own identity is the bytes and the commit it measured, never a folder label. It used to be written
to a single stable path (`evidence-seal.json` inside a directory named after the date the set was first
sealed), which meant a seal from one commit could be re-read as the verdict for the next: the folder name
told you when the set was started, and nothing told you what it judged. The seal is now named
`evidence-seal.g<commit12>.b<bundleDigest16>.json`, carries `gitHead` in its payload, and refuses to be
written at all when the commit cannot be resolved. The directory it reads stays a parameter, because the
cited receipt set physically lives there and several tracked documents quote those paths.

usage: python scripts/audit/seal_wui_evidence.py [--write] [--artifacts-dir DIR]
"""
from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "scripts" / "audit"))
import bundle_provenance  # noqa: E402

# Where the cited receipt set lives. A location, not an identity: the identity of a seal is in its file
# name and payload. Override with `--artifacts-dir` when a re-seal starts a new set.
ARTIFACTS = ROOT / ".project-local" / "artifacts" / "wui-20261009"


def git_head() -> str:
    done = subprocess.run(["git", "-C", str(ROOT), "rev-parse", "HEAD"],
                          capture_output=True, text=True, encoding="utf-8", errors="replace",
                          check=False)
    return done.stdout.strip() or "UNKNOWN"

# The set the register actually cites. An artifact nobody quotes is not evidence and is not sealed.
CITED = (
    "evidence-receipt.json",
    "geometry-freshbundle.json",
    "legibility-allviews-fresh.json",
    "legibility-live-views.json",
    "legibility-dpi-widths.json",
    "legibility-1440.json",
    "display-scaling.json",
    "sse-revision.json",
    "sse-revision-falsify.json",
)

# A ceiling is an artifact the seal reports but never turns red over, because closing it needs something
# this machine does not have. `keyboard-focus-fresh.json` is the native WebView2 keyboard gate, and its own
# verdict line says it never ran: `KEYBOARD_FOCUS_GATE_NOT_RUN reason=no_current_binary: the artifact gate
# says STALE_OR_MISSING_BINARY -- no release app.exe is at least as new as the last content change`. So this
# is not a stale SUCCESS, it is a zero -- and re-running it after a rebuild cannot help, because rebuilding
# `frontend/dist` is exactly what makes every existing binary too old. Relaunching would spend a window to
# reproduce the same NOT_RUN, so the honest state is "named ceiling", not "re-measured".
CEILING = {
    "keyboard-focus-fresh.json": "the native keyboard gate reports KEYBOARD_FOCUS_GATE_NOT_RUN "
                                "(no_current_binary: no release app.exe is at least as new as the last "
                                "front-end content change); it has never produced a verdict here, and a "
                                "rebuild of frontend/dist cannot make one",
}


def claims(node: object, digests: set[str], index_shas: set[str], shots: set[str]) -> None:
    if isinstance(node, dict):
        digest = node.get("bundleDigest")
        if isinstance(digest, str):
            digests.add(digest)
        bundle = node.get("distBundle")
        if isinstance(bundle, dict) and isinstance(bundle.get("sha256"), str):
            index_shas.add(bundle["sha256"])
        target = node.get("screenshot")
        if isinstance(target, str):
            shots.add(Path(target).name)
        for value in node.values():
            claims(value, digests, index_shas, shots)
    elif isinstance(node, list):
        for item in node:
            claims(item, digests, index_shas, shots)


def binding_of(path: Path, current_digest: str, current_index_sha: str) -> tuple[str, str]:
    """(state, detail).

    Two identities a receipt can carry mean two different claims, and the seal must not trade them:
      * `servedBundle.bundleDigest` -- the CDP instruments hashed the files the browser fetched, so this
        names the bytes that RENDERED;
      * `distBundle.sha256` -- the native keyboard gate hashes `frontend/dist/index.html` as a stage 0
        precondition, but the app it launches loads the bundle EMBEDDED in the release binary, which on
        this machine predates the current front end (the instrument says so itself). So that field names
        what was staged, never what was painted.

    BOUND_STAGED is therefore not a pass for a render claim, and is reported as its own state.
    """
    if path.suffix.lower() == ".json":
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, UnicodeDecodeError) as exc:
            return "UNBOUND", f"unreadable JSON: {type(exc).__name__}"
        digests: set[str] = set()
        index_shas: set[str] = set()
        claims(data, digests, index_shas, set())
        if current_digest in digests:
            return "BOUND", f"digest={current_digest[:16]}"
        if digests:
            return "STALE", ("names " + ",".join(sorted(d[:16] for d in digests))
                             + f" but the built bundle is {current_digest[:16]}")
        if current_index_sha in index_shas:
            return "BOUND_STAGED", (f"staged index.html={current_index_sha[:16]} only -- this receipt "
                                    "names what was on disk, not what the launched binary painted")
        if index_shas:
            return "STALE", ("staged " + ",".join(sorted(s[:16] for s in index_shas))
                             + f" but the built index.html is {current_index_sha[:16]}")
        return "UNBOUND", "carries no bundle identity"
    # A screenshot is bound by the receipt that lists it, checked in main().
    return "PICTURE", ""


def pictures_bound_by(receipt_paths: list[Path], current_digest: str) -> dict[str, str]:
    """{png name: digest} for pictures a receipt that names the CURRENT bundle claims to have captured.

    The digest is a parameter, not a lookup: the caller already computed it, and a classifier that reached
    for the real build itself could not be tested against a synthetic one.
    """
    bound: dict[str, str] = {}
    for receipt in receipt_paths:
        if not receipt.is_file():
            continue
        try:
            data = json.loads(receipt.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, UnicodeDecodeError):
            continue
        digests: set[str] = set()
        shots: set[str] = set()
        claims(data, digests, set(), shots)
        if current_digest not in digests:
            continue  # a receipt about a superseded build cannot seal the picture it points at
        for name in shots:
            bound[name] = current_digest
    return bound


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--write", action="store_true", help="write the identity-named evidence seal")
    parser.add_argument("--artifacts-dir", type=Path, default=None,
                        help="the receipt set to seal (default: the set this script has always sealed)")
    args = parser.parse_args()
    artifacts = args.artifacts_dir if args.artifacts_dir else ARTIFACTS

    if not artifacts.is_dir():
        print(f"EVIDENCE_SEAL_NOT_RUN no {artifacts}")
        return 2
    bundle = bundle_provenance.describe(ROOT)
    digest = bundle["bundleDigest"]
    head = git_head()
    index_sha = next(f["sha256"] for f in bundle["files"] if f["path"] == "index.html")
    pictures = pictures_bound_by([artifacts / name for name in CITED if name.endswith(".json")], digest)

    rows = []
    for path in sorted(p for p in artifacts.iterdir() if p.is_file()):
        if path.name == "evidence-seal.json" or path.name.startswith("evidence-seal.g"):
            continue  # the seal describes the set; it is not a member of it
        state, detail = binding_of(path, digest, index_sha)
        if state == "PICTURE":
            owner = pictures.get(path.name)
            state = "BOUND" if owner == digest else ("STALE" if owner else "UNBOUND")
            detail = f"picture, sealed by a receipt naming {owner[:16] if owner else 'nothing'}"
        rows.append({"file": path.name, "bytes": path.stat().st_size,
                     "sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
                     "modifiedAt": time.strftime("%Y-%m-%dT%H:%M:%SZ",
                                                 time.gmtime(path.stat().st_mtime)),
                     "state": state, "detail": detail})

    cited_rows = [row for row in rows if row["file"] in CITED]
    problems = [f"{row['file']} is {row['state']} ({row['detail']})"
                for row in cited_rows if row["state"] not in ("BOUND", "BOUND_STAGED")]
    # A staged-only binding is not a render claim. It is not a failure either, because the machine that
    # could turn it into one needs a fresh Tauri build; it is a ceiling the seal states out loud so nobody
    # reads the receipt as evidence about the bytes that painted.
    staged_only = [row["file"] for row in rows if row["state"] == "BOUND_STAGED"]
    ceilings = [{"file": name, "state": next((row["state"] for row in rows if row["file"] == name),
                                             "MISSING"), "reason": reason}
                for name, reason in CEILING.items()]
    for name in CITED:
        if not any(row["file"] == name for row in rows):
            problems.append(f"{name} is missing from {artifacts}")
    # A seal that cannot name its commit is exactly the reusable verdict this rewrite removes, so it is
    # refused rather than written with a placeholder.
    if head == "UNKNOWN":
        problems.append("gitHead is UNKNOWN: a seal that names no commit can be read as any commit's "
                        "verdict, so nothing is written")

    unbound_extra = [row["file"] for row in rows if row["state"] == "UNBOUND"
                     and row["file"] not in CITED]
    seal = {
        "gate": "WUI evidence seal against the built front end",
        "sealedAt": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "gitHead": head,
        "boundTo": f"commit:{head[:12] if head != 'UNKNOWN' else 'UNKNOWN'}+"
                   f"bundle:{digest[:16]}",
        "bundle": bundle,
        "files": rows,
        "cited": list(CITED),
        "ceilings": ceilings,
        "stagedOnlyClaims": staged_only,
        "uncitedUnbound": unbound_extra,
        "failures": problems,
        "verdictToken": "EVIDENCE_SEAL_PASS" if not problems else "EVIDENCE_SEAL_FAIL",
    }
    out = artifacts / f"evidence-seal.g{head[:12]}.b{digest[:16]}.json"
    if args.write and head != "UNKNOWN":
        out.write_text(json.dumps(seal, ensure_ascii=False, indent=2) + "\n", encoding="utf-8", newline="\n")

    for row in rows:
        print(f"SEAL {row['state']:<7} {row['file']} {row['detail']}")
    for name in staged_only:
        print(f"NOTE staged-only binding: {name} describes the bytes that were staged, not the bytes "
              "the launched binary painted (its embedded bundle predates this build)")
    for row in ceilings:
        print(f"CEILING {row['file']} state={row['state']} reason={row['reason']}")
    for problem in problems:
        print(f"FAIL {problem}")
    counts: dict[str, int] = {}
    for row in rows:
        counts[row["state"]] = counts.get(row["state"], 0) + 1
    print(f"bundle={digest[:16]} files={len(rows)} states={counts} cited={len(cited_rows)}/{len(CITED)}")
    if head == "UNKNOWN":
        print(f"EVIDENCE_SEAL_REFUSE reason=no_git_head seal_not_written intended_path={out}")
    elif args.write:
        print(f"SEAL_OUT {out}")
    else:
        print(f"SEAL_OUT (not written; pass --write; would be {out})")
    print(seal["verdictToken"])
    return 0 if not problems else 1


if __name__ == "__main__":
    raise SystemExit(main())

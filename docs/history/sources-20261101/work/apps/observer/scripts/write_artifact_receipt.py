#!/usr/bin/env python
"""Write a build-time input receipt next to the release binary.

ERR-105's remaining boundary was that a rollback to an older commit leaves
every input matching HEAD, so nothing in the tree evidences a change and a
superseded binary looks current. mtimes and `git diff` cannot see that; a
record of the bytes the build actually consumed can.

This is the build side's job, not the gate's: the writer runs immediately
after the compiler so the receipt attests to a build that was observed, and
`u19_webview_e2e.py` only ever reads it. A missing receipt is not an error —
the gate falls back to its content-evidence rule and says which basis decided.

v2 records two stages: the bytes the compiler consumed (rust, capabilities,
tauri.conf.json, the embedded dist) and the frontend build chain that produced
that bundle (source tree, entry html, vite/ts/postcss/tailwind configs, both
lockfiles, npm's installed-tree manifest). The second stage is what removes
the need for mtime between `frontend/src` and `frontend/dist`.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import re
import subprocess
import sys
import time
from pathlib import Path

RECEIPT_SUFFIX = ".inputs.json"
RECEIPT_SCHEMA = "work-lab/artifact-input-receipt/v2"
# v1 recorded only the bytes the compiler consumed. The frontend chain that
# produced the embedded bundle was outside it, so an uncommitted edit with a
# back-dated mtime still rested on mtime (ERR-105 blind spot 2). v2 adds that
# stage. v1 receipts stay readable — discarding them would unattest a binary
# that is still the current one — but the gate must say which stage each covers.
RECEIPT_SCHEMA_V1 = "work-lab/artifact-input-receipt/v1"


def repo_root(script: Path) -> Path:
    current = script
    for parent in [current, *current.parents]:
        if (parent / ".git").exists() and (parent / "services").is_dir():
            return parent
    raise SystemExit("WRITE_RECEIPT_FAIL cannot locate the WORK-LAB root")


def digest(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def input_files(root: Path, obs: Path) -> list[Path]:
    """Every byte the compiler and tauri-build consume, in one sorted list."""
    groups = [
        sorted((obs / "src-tauri" / "src").rglob("*")),
        sorted((obs / "src-tauri" / "capabilities").rglob("*")),
        [obs / "src-tauri" / "Cargo.toml", obs / "src-tauri" / "Cargo.lock",
         obs / "src-tauri" / "build.rs", obs / "src-tauri" / "tauri.conf.json"],
        sorted((obs / "frontend" / "dist").rglob("*")),
    ]
    files: list[Path] = []
    for group in groups:
        for p in group:
            if p.is_file():
                files.append(p)
    return files


# The stage that produces the bundle the compiler embeds. vite reads the entry
# index.html, the source tree, both transform configs and whatever npm resolved
# into node_modules; a receipt that skips these cannot tell a current bundle
# from one built before the edit that should have rebuilt it.
FRONTEND_CHAIN_FILES = (
    "src",
    "index.html",
    "package.json",
    "package-lock.json",
    "vite.config.ts",
    "tsconfig.json",
    "postcss.config.js",
    "tailwind.config.js",
    "node_modules/.package-lock.json",
)


def frontend_chain_files(root: Path, obs: Path) -> list[Path]:
    """The frontend build chain's own inputs, in one sorted list."""
    frontend = obs / "frontend"
    files: list[Path] = []
    for name in FRONTEND_CHAIN_FILES:
        target = frontend / name
        if target.is_dir():
            files.extend(p for p in sorted(target.rglob("*")) if p.is_file())
        elif target.is_file():
            files.append(target)
    return files


def git_head(root: Path) -> str:
    done = subprocess.run(["git", "-C", str(root), "rev-parse", "HEAD"],
                          capture_output=True, text=True, encoding="utf-8", errors="replace",
                          check=False)
    return done.stdout.strip() or "UNKNOWN"


# Archived native evidence. `src-tauri/target/` is a cargo cache: the workflow restores it, nothing
# uploads it, and a runner deletes it — so a receipt written only there is evidence for as long as the
# cache lives (defect 3). `.project-local/artifacts/` is the declared evidence root, and the commit and
# the binary digest go into the FILE NAME as well as the payload so a reader cannot mistake yesterday's
# verdict for this commit's.
NATIVE_EVIDENCE_DIR = Path(".project-local") / "artifacts" / "native-evidence"
HEAD_PREFIX = 12
SHA_PREFIX = 16
# `kind.g<commit12>.x<exe-sha16>.inputs.json` — the identity is in the name, so a directory listing
# already says which commit each artifact claims, before anyone opens it.
ARCHIVED_NAME = re.compile(r"^(?P<kind>.+)\.g(?P<head>[0-9a-f]{12})\.x(?P<sha>[0-9a-f]{16})"
                           + re.escape(RECEIPT_SUFFIX) + "$")


def archive_native_evidence(root: Path, kind: str, payload: dict,
                            artifacts_dir: Path | None = None) -> Path:
    """Write `payload` into the evidence root under a name that carries its commit and its bytes.

    Refuses a payload that names no commit: an archived artifact that cannot say which tree it describes
    is the stale-evidence problem again, just filed more tidily.
    """
    head = str(payload.get("gitHead", "")).strip()
    if not head or head == "UNKNOWN":
        raise SystemExit(f"WRITE_RECEIPT_ARCHIVE_REFUSED kind={kind} reason=no_git_head_in_payload")
    binary = payload.get("binary") if isinstance(payload.get("binary"), dict) else {}
    exe_sha = str(binary.get("sha256") or payload.get("exeSha256") or "")
    out_dir = artifacts_dir if artifacts_dir is not None else root / NATIVE_EVIDENCE_DIR
    out_dir.mkdir(parents=True, exist_ok=True)
    name = f"{kind}.g{head[:HEAD_PREFIX]}.x{exe_sha[:SHA_PREFIX] or '0' * SHA_PREFIX}{RECEIPT_SUFFIX}"
    out = out_dir / name
    document = dict(payload)
    document["archivedFrom"] = str(root)
    document["archivedAt"] = time.strftime("%Y-%m-%dT%H:%M:%S%z")
    document["commitPrefix"] = head[:HEAD_PREFIX]
    document["archivedName"] = name
    out.write_text(json.dumps(document, indent=2) + "\n", encoding="utf-8")
    return out


def verify_native_evidence(root: Path, expected_head: str,
                           artifacts_dir: Path | None = None) -> list[str]:
    """Every archived native artifact must name the commit it describes — and mean it.

    Three refusals, each one a way an old verdict can pass as a fresh one: nothing archived for this
    commit; a file whose NAME claims one commit while its PAYLOAD says another; a payload with no commit
    at all. Files for other commits stay on disk and are ignored — history is not a defect.
    """
    problems: list[str] = []
    expected = (expected_head or "").strip()
    if not expected or expected == "UNKNOWN":
        return [f"expected head is not a commit: {expected_head!r}"]
    out_dir = artifacts_dir if artifacts_dir is not None else root / NATIVE_EVIDENCE_DIR
    if not out_dir.is_dir():
        return [f"no archived native evidence at {out_dir}"]
    matching = 0
    for path in sorted(out_dir.glob("*.json")):
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, ValueError) as exc:
            problems.append(f"{path.name} is unreadable ({type(exc).__name__})")
            continue
        head = str(payload.get("gitHead", "")).strip()
        if not head or head == "UNKNOWN":
            problems.append(f"{path.name} records no commit — it cannot be evidence about this one")
            continue
        named = ARCHIVED_NAME.match(path.name)
        if named is None:
            problems.append(f"{path.name} does not follow the archived-evidence naming rule "
                            "(kind.g<commit12>.x<exe16>.inputs.json), so nothing binds it to a commit")
            continue
        if named.group("head") != head[:HEAD_PREFIX]:
            problems.append(f"{path.name} names a commit it does not describe: the file name carries "
                            f"g{named.group('head')} but the payload says g{head[:HEAD_PREFIX]}")
            continue
        if head[:HEAD_PREFIX] == expected[:HEAD_PREFIX]:
            matching += 1
    if matching == 0:
        problems.append(f"no archived native evidence describes commit {expected[:HEAD_PREFIX]}")
    return problems


def write_receipt(root: Path, obs: Path, exe: Path) -> dict:
    if not exe.is_file():
        raise SystemExit(f"WRITE_RECEIPT_FAIL no binary at {exe}")
    files = input_files(root, obs)
    if not files:
        raise SystemExit("WRITE_RECEIPT_FAIL no build inputs found")
    chain = frontend_chain_files(root, obs)
    receipt = {
        "schemaVersion": RECEIPT_SCHEMA,
        "writtenAt": time.strftime("%Y-%m-%dT%H:%M:%S%z"),
        "gitHead": git_head(root),
        "binary": {"path": str(exe), "bytes": exe.stat().st_size,
                   "sha256": digest(exe)},
        "inputCount": len(files),
        "inputs": [{"path": p.relative_to(root).as_posix(),
                    "bytes": p.stat().st_size, "sha256": digest(p)}
                   for p in files],
        "frontendInputCount": len(chain),
        "frontendInputs": [{"path": p.relative_to(root).as_posix(),
                            "bytes": p.stat().st_size, "sha256": digest(p)}
                           for p in chain],
    }
    out = exe.with_name(exe.name + RECEIPT_SUFFIX)
    out.write_text(json.dumps(receipt, indent=2) + "\n", encoding="utf-8")
    receipt["receiptPath"] = str(out)
    archived = archive_native_evidence(root, "app-receipt", receipt)
    receipt["archivedReceiptPath"] = str(archived)
    return receipt


def main() -> int:
    here = Path(__file__).resolve()
    root = repo_root(here)
    obs = root / "apps" / "observer"
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--exe", default=None,
                    help="the binary just built; defaults to "
                         "$CARGO_TARGET_DIR or src-tauri/target release/app.exe")
    ap.add_argument("--verify-against", default=None, metavar="COMMIT",
                    help="do not write: check that the archived native evidence names this commit "
                         "(CI passes github.sha) and exit 1 if any of it describes a different tree")
    args = ap.parse_args()
    if args.verify_against:
        expected = args.verify_against
        if expected in ("", "HEAD"):
            expected = git_head(root)
        problems = verify_native_evidence(root, expected)
        for problem in problems:
            print(f"NATIVE_EVIDENCE_REFUSE {problem}")
        if problems:
            print(f"NATIVE_EVIDENCE_FAIL problems={len(problems)} "
                  f"root={root / NATIVE_EVIDENCE_DIR}")
            return 1
        print(f"NATIVE_EVIDENCE_PASS commit={expected[:HEAD_PREFIX]} "
              f"dir={root / NATIVE_EVIDENCE_DIR}")
        return 0
    if args.exe:
        exe = Path(args.exe)
    else:
        import os
        target = os.environ.get("CARGO_TARGET_DIR")
        base = Path(target) if target else obs / "src-tauri" / "target"
        if not base.is_absolute():
            base = Path.cwd() / base
        exe = base / "release" / "app.exe"
    receipt = write_receipt(root, obs, exe)
    print(f"WRITE_RECEIPT_OK exe={receipt['binary']['sha256'][:16]} "
          f"inputs={receipt['inputCount']} "
          f"frontendInputs={receipt['frontendInputCount']} "
          f"gitHead={receipt['gitHead'][:9]} "
          f"receipt={receipt['receiptPath']} "
          f"archived={receipt['archivedReceiptPath']}")
    return 0


if __name__ == "__main__":
    sys.exit(main())

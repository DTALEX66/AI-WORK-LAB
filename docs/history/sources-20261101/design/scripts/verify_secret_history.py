#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""DL-CLOUDAUDIT-B1 — secret history scanner (crosswalk G-1 / cloud audit R12).

The supply-chain gate (G040_secret_scan) scans the tracked files at HEAD only.
A credential that was committed, branched away, or force-pushed still lives in
the object graph. This scanner runs the SAME patterns and the SAME synthetic /
adjudication exemption rules (imported from verify_supply_chain — never a
second set) over every distinct blob revision in `git rev-list --objects
--all`, deduplicated by blob sha so each distinct value is scanned once.

Redaction contract: the report stores only the value's sha256 digest plus a
3-char prefix / 3-char suffix; the full value never enters the report.

Fail-closed: a git failure, an unreadable object, or a cap violation is a
FAILED run, not a silent PASS.

Usage:
    python scripts/verify_secret_history.py [--head-only] [--max-blobs N]

Exit codes: 0 PASS, 1 FAIL (hits, git/IO failures, or scope capped).
"""
from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from scripts.verify_supply_chain import (  # noqa: E402  single source of rules
    REPO,
    SECRET_PATTERNS,
    is_synthetic,
    load_adjudications,
)

OUT = REPO / "reports/current/SECRET-HISTORY-REPORT.json"
SELF_OUTPUT_REL = "reports/current/SECRET-HISTORY-REPORT.json"
MAX_BLOB_BYTES = 1_000_000  # matches G040's per-file size bound
DEFAULT_MAX_BLOBS = 4000

def git(*args: str) -> str:
    proc = subprocess.run(["git", "-C", str(REPO), *args], capture_output=True,
                          text=True, encoding="utf-8", errors="replace")
    if proc.returncode != 0:
        raise RuntimeError(f"git {' '.join(args)} failed: {proc.stderr.strip()[:300]}")
    return proc.stdout


def git_quiet(*args: str) -> str:
    """Variant that returns '' instead of raising (used for path existence)."""
    proc = subprocess.run(["git", "-C", str(REPO), *args], capture_output=True,
                          text=True, encoding="utf-8", errors="replace")
    return proc.stdout.strip() if proc.returncode == 0 else ""


def blob_map_head_only() -> dict[str, set[str]]:
    """(path -> {blob sha}) for the HEAD tree only.

    `ls-tree -r HEAD` rows are "<mode> <type> <sha>\t<path>": the object
    id is the third space-separated field, the path follows the tab.
    """
    by_path: dict[str, set[str]] = {}
    for line in git("ls-tree", "-r", "HEAD").splitlines():
        meta, _, path = line.partition("\t")
        fields = meta.split(" ")
        if len(fields) != 3 or fields[1] != "blob" or not path:
            continue
        by_path.setdefault(path, set()).add(fields[2])
    return by_path


def blob_map_all() -> dict[str, set[str]]:
    """(path -> {blob sha}) across every ref; distinct revisions deduplicated.

    `rev-list --objects` lines are "<sha> <path>" (sha first); tree and
    commit ids carry the empty path and are dropped here — they are counted
    as skips by the scanner, and the empty-path rows never reach it.
    """
    by_path: dict[str, set[str]] = {}
    for line in git("rev-list", "--objects", "--all").splitlines():
        if " " not in line:
            continue
        sha, path = line.split(" ", 1)
        if not path:
            continue
        by_path.setdefault(path, set()).add(sha)
    return by_path


def scan_blob_map(by_path: dict[str, set[str]], fetch_blob, adjudications: dict) -> dict:
    """Pure core: scan every distinct blob revision; no git, no IO.

    `fetch_blob(path, blob) -> (kind, data | None)` where kind is "blob",
    "tree", "commit" or "missing". `rev-list --objects` mixes in tree and
    commit ids, so those are counted as skipped, not failures. A "missing"
    object (the revision should exist but cannot be read) is fail-closed:
    it is recorded as a failure, never a silent skip. Exemption and
    pattern rules come from verify_supply_chain so the history scan can
    never drift from the HEAD scan.
    """
    failures: list[str] = []
    hits: list[dict] = []
    exempted = 0
    adjudicated = 0
    scanned = 0
    skipped_oversize = 0
    skipped_binary = 0
    skipped_nontype = 0
    unreadable = 0

    for path in sorted(by_path):
        if path == SELF_OUTPUT_REL:
            continue
        for blob in sorted(by_path[path]):
            kind, data = fetch_blob(path, blob)
            if kind == "missing":
                unreadable += 1
                failures.append(f"unfetchable blob {path}@{blob}")
                continue
            if kind == "oversize":
                skipped_oversize += 1
                continue
            if kind != "blob":
                # tree / commit ids from `rev-list --objects`: skipped, not failures
                skipped_nontype += 1
                continue
            if len(data) > MAX_BLOB_BYTES:
                skipped_oversize += 1
                continue
            try:
                text = data.decode("utf-8")
            except UnicodeDecodeError:
                skipped_binary += 1
                continue
            scanned += 1
            for name, pattern in SECRET_PATTERNS:
                for match in pattern.finditer(text):
                    value = match.group(0)
                    digest = "sha256:" + hashlib.sha256(value.encode()).hexdigest()
                    if digest in adjudications:
                        adjudicated += 1
                        continue
                    if is_synthetic(path, value):
                        exempted += 1
                        continue
                    hits.append({
                        "pattern": name,
                        "path": path,
                        "blob_sha": blob,
                        "value_sha256": digest,
                        "value_redacted": (value[:3] + "…" + value[-3:]
                                           if len(value) > 7 else "***"),
                    })
    return {
        "blob_revisions_scanned": scanned,
        "skipped_oversize": skipped_oversize,
        "skipped_binary": skipped_binary,
        "skipped_tree_or_commit": skipped_nontype,
        "unfetchable_blobs": unreadable,
        "exempted_synthetic": exempted,
        "exempted_adjudicated": adjudicated,
        "hits": hits,
        "failures": failures,
    }


def _run_git(input_text: bytes | None, *args: str, repo) -> bytes:
    """`git -C repo <args>` via subprocess.run: one bulk stdin write and a
    C-level read-to-EOF.

    Per-request `write+flush` into a long-lived `cat-file` pipe is
    unreliable on Windows (adjacent writes coalesce and the reply stream
    desyncs), so each phase is a single child process with the whole
    payload on its stdin. `--batch-check` replies with one header line
    per requested id; `--batch` replies with headers and bodies
    interleaved in request order, terminated by EOF — parse in memory.

    subprocess.run drives both pipes through communicate(), so the
    stderr buffer can never deadlock a read-to-EOF. Output stays binary
    — blob bodies may contain NUL bytes that text decoding would corrupt.
    """
    cmd = ["git", "-C", str(repo), *args]
    proc = subprocess.run(cmd, input=input_text, capture_output=True,
                          check=False)
    if proc.returncode != 0:
        raise RuntimeError(f"git {' '.join(args)} failed: {proc.stderr[:300]}")
    return proc.stdout


def make_batch_fetcher() -> callable:
    """Return (prefetch, fetch_blob, cleanup); one child process per phase.

    `prefetch(ids)` classifies every id with `git cat-file --batch-check`
    (header-only, safe for any object type) and then pulls the confirmed
    in-bound bodies in a single `git cat-file --batch` call. Both payloads
    go out over stdin in one bulk write and come back via a C-level
    read-to-EOF, so there is no per-object pipe round trip.
    `fetch_blob(path, blob)` answers purely from the caches; an in-bound
    blob without a cached body is "missing" (fail-closed), never dropped.

    kind is one of {"blob","tree","commit","missing","oversize"}.
    """
    classified: dict[str, tuple[str, int]] = {}
    bodies: dict[str, bytes | None] = {}

    def prefetch(ids: list[str]) -> None:
        if not ids:
            return
        out = _run_git("".join(i + "\n" for i in ids).encode(),
                       "cat-file", "--batch-check", repo=REPO)
        lines = out.split(b"\n")
        for i, raw in zip(ids, lines):
            parts = raw.split()
            classified[i] = (parts[1].decode("ascii"), int(parts[2])) \
                if len(parts) == 3 else ("missing", 0)
        blob_ids = [i for i in ids
                    if classified[i][0] == "blob" and classified[i][1] <= MAX_BLOB_BYTES]
        if not blob_ids:
            return
        stream = _run_git("".join(i + "\n" for i in blob_ids).encode(),
                          "cat-file", "--batch", repo=REPO)
        # Record layout: "<id> <type> <size>\n<body>" per record. Some git
        # builds (observed on this Windows host) emit an extra boundary byte
        # after each body, so a parser assuming the exact standard layout
        # desyncs from record 2 on. The parser therefore (a) skips stray
        # inter-record \n/\r bytes and (b) verifies every echoed id against
        # the request order; any mismatch fails the whole run closed.
        pos = 0
        for i in blob_ids:
            end = len(stream)
            while pos < end and stream[pos:pos + 1] in (b"\n", b"\r"):
                pos += 1
            nl = stream.find(b"\n", pos)
            if nl == -1:
                bodies[i] = None  # stream ended short: fail-closed
                break
            header = stream[pos:nl].split()
            if len(header) >= 1 and header[0].decode("ascii", "replace") == i:
                pos = nl + 1
                if len(header) == 3 and header[1] == b"blob":
                    size = int(header[2])
                    body = stream[pos:pos + size]
                    bodies[i] = body if len(body) == size else None
                    pos += size
                else:
                    bodies[i] = None  # "missing" reply (no body)
            else:
                # id echo mismatch: any deeper desync. Fail closed — do not
                # guess a resync point, mark this and the rest unreadable.
                bodies[i] = None
                break

    def fetch_blob(path: str, blob: str) -> tuple[str, bytes | None]:
        if blob in bodies:
            body = bodies[blob]
            if body is None:
                return ("missing", None)
            return ("blob", body)
        kind, size = classified.get(blob, ("missing", 0))
        if kind != "blob":
            return (kind, None)
        if size > MAX_BLOB_BYTES:
            return ("oversize", None)
        return ("missing", None)  # in-bound blob never prefetched

    def cleanup() -> None:
        """No live processes to reap; the caches are plain dicts."""

    return prefetch, fetch_blob, cleanup


def main_ok(result: dict) -> bool:
    """The core's own ok flag: no hits, no git failures."""
    return not result["hits"] and not result["failures"]


def _introducing_commit(blob: str, path: str) -> str:
    out = git_quiet("log", "--follow", "--format=%H", "HEAD", "--", path).split()
    if not out:
        return "(not in HEAD path history)"
    for commit in reversed(out):
        if git_quiet("rev-parse", f"{commit}:{path}") == blob:
            return commit[:12]
    return f"(predates path history; oldest={out[-1][:12]})"


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--head-only", action="store_true",
                        help="scan only the HEAD tree (one rev-list pass, cheaper)")
    parser.add_argument("--max-blobs", type=int, default=DEFAULT_MAX_BLOBS,
                        help="cap on distinct blob revisions (default "
                             f"{DEFAULT_MAX_BLOBS}; 0 = unlimited; hitting the cap "
                             "is a FAIL, never a silent shrink)")
    args = parser.parse_args(argv)

    import time as _time
    t0 = _time.time()
    by_path = blob_map_head_only() if args.head_only else blob_map_all()
    total = sum(len(v) for v in by_path.values())
    print(f"[phase] enum {total} distinct revisions in {_time.time()-t0:.1f}s", flush=True)
    if args.max_blobs and total > args.max_blobs:
        print(f"SECRET_HISTORY=FAIL scope: {total} distinct blob revisions exceed "
              f"--max-blobs {args.max_blobs}; raise the cap explicitly, "
              "do not silently shrink the scan")
        return 1

    adjudications, malformed = load_adjudications()
    prefetch, fetch_blob, cleanup = make_batch_fetcher()
    try:
        all_ids = sorted({blob for blobs in by_path.values() for blob in blobs})
        t1 = _time.time()
        prefetch(all_ids)
        print(f"[phase] prefetch {len(all_ids)} ids in {_time.time()-t1:.1f}s", flush=True)
        t2 = _time.time()
        result = scan_blob_map(by_path, fetch_blob, adjudications)
        print(f"[phase] scan {result['blob_revisions_scanned']} blobs in {_time.time()-t2:.1f}s "
              f"hits={len(result['hits'])} failures={len(result['failures'])}", flush=True)
    finally:
        cleanup()

    for hit in result["hits"]:
        hit["introduced_in"] = _introducing_commit(hit["blob_sha"], hit["path"])

    document = {
        "schemaVersion": "design-lab/secret-history-report/v1",
        "task_keys": ["DL-CLOUDAUDIT-20260923::B1"],
        "generated_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "subject_sha": git("rev-parse", "HEAD").strip(),
        "mode": "head-only" if args.head_only else "all-revisions",
        "blob_revisions_scanned": result["blob_revisions_scanned"],
        "skipped_oversize": result["skipped_oversize"],
        "skipped_binary": result["skipped_binary"],
        "skipped_tree_or_commit": result["skipped_tree_or_commit"],
        "unfetchable_blobs": result["unfetchable_blobs"],
        "exempted_synthetic": result["exempted_synthetic"],
        "exempted_adjudicated": result["exempted_adjudicated"],
        "malformed_adjudications": malformed,
        "hits": result["hits"][:50],
        "hit_count": len(result["hits"]),
        "git_failures": result["failures"],
        "redaction_contract":
            "reports store only the value sha256 + 3/3-char ends, never the value",
        "ok": (not result["hits"] and not malformed
               and not result["failures"]),
    }
    # Resolved from REPO at call time (not the import-time constant) so tests
    # can redirect the repository root without writing into the real one.
    out_path = REPO / "reports/current/SECRET-HISTORY-REPORT.json"
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(document, indent=2, ensure_ascii=False) + "\n",
                        encoding="utf-8", newline="\n")
    print(f"SECRET_HISTORY={'PASS' if document['ok'] else 'FAIL'} mode={document['mode']} "
          f"scanned={document['blob_revisions_scanned']} hits={len(result['hits'])} "
          f"failures={len(result['failures'])}")
    for h in document["hits"][:10]:
        print(f"  HIT {h['pattern']} {h['path']}@{h['blob_sha'][:12]} "
              f"value={h['value_sha256'][:19]}… "
              f"redacted='{h['value_redacted']}' introduced_in={h['introduced_in']}")
    for f in result["failures"][:5]:
        print("  FAIL", f)
    return 0 if document["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())

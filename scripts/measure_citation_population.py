#!/usr/bin/env python
"""Measure two citation populations over the tracked tree, and say who owns each byte.

Both numbers in this project's entry document come out of here, for a specific reason: measured once by
an ad-hoc script under ``.project-local`` a figure is unreviewable from a clone, and two such figures
have already been wrong in this way -- "322 tracked files contain the machine account name" (a loose
substring match that also counted the public repo owner ``DTALEX66``, which contains the same letters)
and "621 prose ``.py:line`` cites" (a count whose exclusions differed between runs). A measurement a
reader cannot re-run is a claim, so this tool is tracked, deterministic (no timestamps, no machine
paths in its output) and refuses loudly instead of returning a reassuring zero.

Populations:
  * ``line_cites``   -- ``<path>.py:123`` (optionally a range) mentions of Python line numbers,
                        including the ones in prose, which no register guard resolves.
  * ``machine_names`` -- mentions of this checkout's OS account name, split into standalone tokens,
                        whole absolute machine paths, and the repo-owner token that must not be
                        confused with either.

Ownership comes from the ledgers (``migration/copies.json`` and the history MANIFEST), matched at
prefix boundaries: an earlier version used ``endswith`` and claimed ``AGENTS.md`` was a byte-for-byte
copy of a source-repo file, which is how a probe manufactures a wrong bucket.

    python -B -X utf8 scripts/measure_citation_population.py
    python -B -X utf8 scripts/measure_citation_population.py --json-out out.json
"""
from __future__ import annotations

import argparse
import csv
import json
import os
import pathlib
import re
import subprocess
import sys

REPO_ROOT = pathlib.Path(__file__).resolve().parents[1]
COPIES = REPO_ROOT / "migration" / "copies.json"
MANIFEST = REPO_ROOT / "docs" / "history" / "sources-20261101" / "MANIFEST.csv"
# owner-delivered task pack and the October authority snapshots: records, not our prose
FROZEN_INPUTS = ("docs/audits-20261103-cloud-audit/", "docs/authority-202610/", "docs/history/")
APPEND_ONLY = ("docs/CODEX-AUDIT-ENTRY.md",)
GENERATED = ("migration/", "config/")
OUR_OWN_CODE = ("scripts/", "tests/", "backend/", "domains/work/")

LINE_CITE = re.compile(r"[\w./-]+\.py:\d+(?:-\d+)?")
ABS_WIN = r"[A-Za-z]:[\\/][^\s\"'`<|]*"
ABS_POSIX = r"(?:/home|/Users)/"


def account_name() -> str:
    """This checkout's OS account name, or "" when it cannot be determined -- never a guess."""
    home = str(pathlib.Path.home())
    tail = re.split(r"[\\/]", home.strip("\\"))[-1]
    return tail if len(tail) >= 2 else ""


def tracked_files() -> list[str]:
    listed = subprocess.run(["git", "ls-files", "-z"], cwd=str(REPO_ROOT), capture_output=True,
                            check=True).stdout
    return [p.decode("utf-8", "replace") for p in listed.split(b"\0") if p]


def read_tracked_text(path: pathlib.Path):
    """Text of a tracked byte, or None when the disk refuses -- which the caller must report.

    ``D:\\``-style paths stop at 259 characters, so a deep frozen input reads as
    ``FileNotFoundError`` on the path the index actually stores. The long-form prefix is tried before
    anything is called absent, because an earlier instrument of exactly this shape dropped 860 cites by
    skipping files it never mentioned.
    """
    try:
        return path.read_text(encoding="utf-8", errors="replace")
    except OSError:
        if os.name != "nt":
            return None
        try:
            with open("\\\\?\\" + str(path.absolute()), "r", encoding="utf-8",
                      errors="replace") as handle:
                return handle.read()
        except OSError:
            return None


def to_relative(value: str) -> str:
    value = (value or "").replace("\\", "/").strip()
    if not value:
        return ""
    marker = REPO_ROOT.name + "/"
    if marker in value:
        return value.split(marker, 1)[1].lstrip("/")
    return value.lstrip("/")


def ledger_targets() -> set[str]:
    """Relative paths the ledgers claim as copies -- read for shape, never assumed."""
    if not COPIES.is_file():
        # str(), not relative_to(): a caller may point these at a sandbox, and a traceback is not a
        # named refusal
        raise SystemExit("MEASUREMENT_LEDGER_ABSENT: %s" % COPIES)
    claimed: set[str] = set()
    document = json.loads(COPIES.read_text(encoding="utf-8-sig"))
    if not isinstance(document, dict) or "copies" not in document:
        raise SystemExit("MEASUREMENT_LEDGER_SHAPE: %s 没有 copies 键，无法判定归属"
                         % COPIES)
    for row in document.get("copies", []):
        target = to_relative(row.get("target", ""))
        if target:
            claimed.add(target)
        for record in row.get("records") or []:
            nested = to_relative(record.get("target", ""))
            if nested:
                claimed.add(nested)
    for row in document.get("patches", []):
        if row.get("file"):
            claimed.add(to_relative(row["file"]))
    for row in document.get("inits", []):
        if isinstance(row, str) and row:
            claimed.add(to_relative(row))
    if MANIFEST.is_file():
        with MANIFEST.open(encoding="utf-8-sig", newline="") as handle:
            for row in csv.DictReader(handle):
                target = to_relative(row.get("target_rel") or "")
                if target:
                    claimed.add(target)
    else:
        # the manifest is the second of the two ownership sources; without it a file under a copied
        # tree could be read as ours, so this is a named gap rather than a quiet narrower scan
        # the second ownership source; without it a file under a copied tree would be read as our
        # own prose, which is how a rewrite of a frozen record gets looks-legitimate. str(), not
        # relative_to(): a caller may point these at a sandbox, and a traceback is not a refusal.
        raise SystemExit("MEASUREMENT_LEDGER_ABSENT: %s" % MANIFEST)
    return claimed


def owner_of(relative: str, claimed: set[str]) -> str:
    """Which of the four kinds of custody this byte stream is under -- boundaries, not suffixes."""
    if relative.startswith(APPEND_ONLY):
        return "append_only_history"
    if relative.startswith(FROZEN_INPUTS):
        return "frozen_source_input"
    if any(relative == target or relative.startswith(target + "/") for target in claimed):
        return "migrated_copy"
    if relative.startswith(GENERATED):
        return "generated_register"
    if relative.startswith(OUR_OWN_CODE):
        return "own_code_and_checks"
    return "own_other"


OWNERSHIPS = ("append_only_history", "frozen_source_input", "migrated_copy", "generated_register",
              "own_code_and_checks", "own_other")


def measure(root: pathlib.Path = REPO_ROOT, account: str | None = None,
            claimed: set[str] | None = None, files: list[str] | None = None) -> dict:
    """The two populations, bucketed by custody, over the tracked tree of ``root``."""
    root = pathlib.Path(root)
    account = account_name() if account is None else account
    if not account:
        raise SystemExit("MEASUREMENT_PREREQ_MISSING: 这台机器的账号名无法确定，"
                         "账号名人群不做（返回 0 会被读成「没有泄漏」）")
    claimed = ledger_targets() if claimed is None else claimed
    bare = re.compile(r"(?<![A-Za-z0-9_.\-/])" + re.escape(account) + r"(?![A-Za-z0-9_.\-/])")
    owner_token = re.compile(r"\bDTALEX66\b")
    abs_path = re.compile(r"(?:%s%s[\\/]|%s%s/)" % (ABS_WIN, re.escape(account), ABS_POSIX,
                                                    re.escape(account)))
    if files is None:
        listed = subprocess.run(["git", "ls-files", "-z"], cwd=str(root), capture_output=True,
                                check=True).stdout
        files = [row.decode("utf-8", "replace") for row in listed.split(b"\0") if row]
    buckets = {kind: {"files": 0, "line_cites": 0, "account_mentions": 0,
                      "absolute_machine_paths": 0, "paths": []} for kind in OWNERSHIPS}
    unreadable: list[str] = []
    scanned = 0
    for relative in sorted(files):
        text = read_tracked_text(root / relative)
        if text is None:
            unreadable.append(relative)
            continue
        scanned += 1
        kind = owner_of(relative, claimed)
        bucket = buckets[kind]
        cites = len(LINE_CITE.findall(text))
        mentions = len(bare.findall(text))
        absolute = len(abs_path.findall(text))
        bucket["line_cites"] += cites
        bucket["account_mentions"] += mentions
        bucket["absolute_machine_paths"] += absolute
        if cites or mentions or absolute:
            bucket["files"] += 1
            if len(bucket["paths"]) < 12:
                bucket["paths"].append(relative)
    return {"files_scanned": scanned, "files_tracked": len(files),
            "files_unreadable": len(unreadable),
            "unreadable_paths": unreadable[:12],
            "account_name_length": len(account),
            "ledger_claimed_targets": len(claimed),
            "totals": {key: sum(bucket[key] for bucket in buckets.values())
                       for key in ("files", "line_cites", "account_mentions",
                                   "absolute_machine_paths")},
            "by_ownership": {key: {field: value for field, value in bucket.items()
                                   if field != "paths"}
                             for key, bucket in buckets.items()},
            "samples": {key: bucket["paths"] for key, bucket in buckets.items() if bucket["paths"]}}


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--json-out", type=pathlib.Path)
    args = parser.parse_args(argv)
    document = measure()
    payload = json.dumps(document, ensure_ascii=False, indent=2, sort_keys=True)
    if args.json_out:
        args.json_out.write_text(payload + "\n", encoding="utf-8", newline="\n")
    print(payload)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

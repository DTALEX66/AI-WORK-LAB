#!/usr/bin/env python3
"""Classify every commit pin in the open task register by whether a reader can actually check it out.

Three states matter and they are not the same question:

  ON_MAIN        an ancestor of origin/main -- the strongest form, survives anything
  OTHER_REF      contained in some ref that is not main -- legitimate while a PR branch is open,
                 and the reason an earlier "not on main" count of 40 was not a list of 40 defects
  ZERO_REFS      the object parses and `git log` answers for it, but no ref contains it: a reader
                 who follows the pin gets a detached checkout that belongs to nothing, which is what
                 squash-merged PR heads become

`--check` exits 1 when any pin is in ZERO_REFS, so the register can be held to it. The token regex
requires a preceding `@` because the register writes `IMPLEMENTED@0600d6f`; bare hashes in prose are
not pins.
"""
from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
from pathlib import Path

REGISTER = Path("taskpacks/current/OPEN-TASK-REGISTER.md")
PIN = re.compile(r"@([0-9a-f]{7,40})\b")
ROW = re.compile(r"^\|\s*([^|]+?)\s*\|")


def repo_root() -> Path:
    current = Path(__file__).resolve()
    for parent in [current, *current.parents]:
        if (parent / ".git").exists() and (parent / "services").is_dir():
            return parent
    raise SystemExit("PIN_REACHABILITY_FAIL cannot locate WORK-LAB root")


def git(root: Path, *args: str) -> str:
    return subprocess.run(["git", *args], cwd=root, capture_output=True).stdout.decode(
        "utf-8", "replace").strip()


def classify(root: Path, token: str) -> tuple[str, str, list[str]]:
    full = git(root, "rev-parse", "--verify", f"{token}^{{commit}}")
    if len(full) != 40:
        return "UNRESOLVABLE", "", []
    refs = git(root, "for-each-ref", f"--contains={full}", "--format=%(refname)").split()
    on_main = subprocess.run(["git", "merge-base", "--is-ancestor", full, "origin/main"],
                             cwd=root, capture_output=True).returncode == 0
    if on_main:
        return "ON_MAIN", full, refs
    if not refs:
        return "ZERO_REFS", full, refs
    return "OTHER_REF", full, refs


def rows_with_pins(text: str) -> list[tuple[int, str, list[str]]]:
    rows = []
    current_row = ""
    for number, line in enumerate(text.splitlines(), 1):
        if line.startswith("|"):
            match = ROW.match(line)
            current_row = match.group(1) if match else ""
        tokens = PIN.findall(line)
        if tokens:
            rows.append((number, current_row, sorted(set(tokens))))
    return rows


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--register", default=str(REGISTER))
    ap.add_argument("--repo", default=None,
                    help="the repository whose objects decide a pin's reachability. A test may point it at a "
                         "scratch repo where the dangling-commit case is CONSTRUCTED, because an object that "
                         "exists only in the author's clone is a different state on a fresh one")
    ap.add_argument("--check", action="store_true", help="exit 1 when a pin is contained by no ref")
    ap.add_argument("--out", default=None)
    args = ap.parse_args(argv)

    root = Path(args.repo).resolve() if args.repo else repo_root()
    path = Path(args.register)
    if not path.is_absolute():
        path = root / path
    if not path.is_file():
        print(f"PIN_REACHABILITY_FAIL missing {path}")
        return 1

    text = path.read_text(encoding="utf-8")
    rows = rows_with_pins(text)
    if not rows:
        print(f"PIN_REACHABILITY_FAIL rows_with_pins=0 in {path.name} -- the extractor matched "
              "nothing, which is a broken checker rather than a clean register")
        return 1

    seen: dict[str, tuple[str, str, list[str]]] = {}
    records = []
    for number, row_id, tokens in rows:
        for token in tokens:
            if token not in seen:
                seen[token] = classify(root, token)
            state, full, refs = seen[token]
            records.append({"row": row_id, "line": number, "token": token, "fullCommit": full,
                            "state": state, "containingRefs": refs[:6],
                            "containingRefCount": len(refs)})

    counts: dict[str, int] = {}
    for record in records:
        counts[record["state"]] = counts.get(record["state"], 0) + 1
    tokens = sorted(seen)
    dangling = sorted({r["token"] for r in records if r["state"] == "ZERO_REFS"})
    unresolvable = sorted({r["token"] for r in records if r["state"] == "UNRESOLVABLE"})
    rows_dangling = sorted({r["row"] for r in records if r["state"] == "ZERO_REFS"})

    flag = "PASS" if not dangling and not unresolvable else "FAIL"
    print(f"PIN_REACHABILITY_{flag} pins={len(records)} distinct_tokens={len(tokens)} "
          f"rows_with_pins={len(rows)} " + " ".join(f"{k}={v}" for k, v in sorted(counts.items())))
    for token in dangling:
        first = next(r for r in records if r["token"] == token)
        print(f"  ZERO_REFS {token} ({first['fullCommit'][:12]}…) cited by rows: "
              + ", ".join(sorted({r["row"] for r in records if r["token"] == token})))
    for token in unresolvable:
        print(f"  UNRESOLVABLE {token} -- no such commit object")
    if args.out:
        Path(args.out).write_text(json.dumps(
            {"schemaVersion": "work-lab/register-pin-reachability/v1",
             "register": path.as_posix(), "counts": counts,
             "distinctTokens": tokens, "zeroRefTokens": dangling,
             "unresolvableTokens": unresolvable, "rowsWithZeroRefs": rows_dangling,
             "records": records}, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8", newline="\n")
        print(f"report -> {args.out}")
    if args.check and (dangling or unresolvable):
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

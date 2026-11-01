#!/usr/bin/env python3
"""Every row of a register table must have the cell count its own header declares.

A Work cell that contains a piped shell command inside backticks is read by markdown as extra columns:
the sentence splits at the first unescaped `|` and everything after it leaves the visible table. Nine rows
in this register were in that state today -- two of them written by me this session -- and nothing looked.
Cell splitting is escape-aware (`\\|` is content), which is the difference between judging a row and
counting the pipes inside its own evidence.
"""
from __future__ import annotations

import argparse
import re
from pathlib import Path

DEFAULT_REGISTER = Path("taskpacks/current/OPEN-TASK-REGISTER.md")
CELLS = re.compile(r"(?<!\\)\|")
SEPARATOR = re.compile(r"^\|[\s:|-]+\|$")


def repo_root() -> Path:
    current = Path(__file__).resolve()
    for parent in [current, *current.parents]:
        if (parent / ".git").exists() and (parent / "services").is_dir():
            return parent
    raise SystemExit("REGISTER_TABLE_SHAPE_FAIL cannot locate WORK-LAB root")


def cells_of(line: str) -> list[str]:
    return [c.strip() for c in CELLS.split(line.strip().strip("|"))]


def scan(text: str) -> tuple[list[tuple[int, int, str]], list[tuple[str, int]], int]:
    """(rows with the wrong width, tables seen, row count)."""
    bad: list[tuple[int, int, str]] = []
    tables: list[tuple[str, int]] = []
    rows = 0
    expected: int | None = None
    for number, line in enumerate(text.splitlines(), 1):
        stripped = line.strip()
        if not stripped.startswith("|"):
            expected = None
            continue
        if SEPARATOR.match(stripped):
            continue
        width = len(cells_of(stripped))
        if expected is None:
            expected = width
            tables.append((stripped[:40], width))
            continue
        rows += 1
        if width != expected:
            bad.append((number, width, cells_of(stripped)[0][:36]))
    return bad, tables, rows


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--register", default=str(DEFAULT_REGISTER))
    args = ap.parse_args(argv)
    root = repo_root()
    path = Path(args.register)
    if not path.is_absolute():
        path = root / path
    if not path.is_file():
        print(f"REGISTER_TABLE_SHAPE_FAIL missing {path}")
        return 1

    bad, tables, rows = scan(path.read_text(encoding="utf-8"))
    if not tables:
        print(f"REGISTER_TABLE_SHAPE_FAIL {path.name} has no pipe table -- nothing was judged, "
              "which is a broken checker rather than a clean register")
        return 1
    if not rows:
        print(f"REGISTER_TABLE_SHAPE_FAIL tables={len(tables)} rows=0 -- headers with no rows are "
              "not a register")
        return 1
    flag = "FAIL" if bad else "PASS"
    print(f"REGISTER_TABLE_SHAPE_{flag} file={path.as_posix()} tables={len(tables)} rows={rows} "
          f"wrong_width={len(bad)}")
    for number, width, first in bad:
        print(f"  line {number}: `{first}` has {width} cells")
    return 1 if bad else 0


if __name__ == "__main__":
    raise SystemExit(main())

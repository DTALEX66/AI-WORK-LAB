"""Proof instrument: the licence audit as it first shipped contradicted its own entries.

Not a CI gate — exit 1 IS the finding, and that is the point. The first version of
`docs/audits/LICENCE_READBACK_2026-10-07.json` said in prose that only three rows were confirmed by
opening the licence file, while the very same document's `method` fields listed six. A reader who
trusted the sentence would have re-fetched three files and trusted eleven. This script reads the
audit **as committed at the revision that introduced it** (a tracked blob, so it does not depend on
any scratch directory or on the working tree) and shows the two numbers disagreeing.

Usage: python scripts/audit/prove_previous_licence_audit_miscounted_the_files.py [REV]
Exit: 1 when the historical text is contradicted by its own data (the defect), 0 if it agrees,
      2 when the revision or file cannot be read.
"""
from __future__ import annotations

import json
import re
import subprocess
import sys
from collections import Counter
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
AUDIT = "docs/audits/LICENCE_READBACK_2026-10-07.json"


def blob_at(rev: str, rel: str) -> bytes | None:
    r = subprocess.run(["git", "show", f"{rev}:{rel}"], cwd=REPO, capture_output=True)
    return r.stdout if r.returncode == 0 else None


def main() -> int:
    rev = sys.argv[1] if len(sys.argv) > 1 else "HEAD~1"
    raw = blob_at(rev, AUDIT)
    if raw is None:
        print(f"CANNOT_READ {AUDIT} at {rev}")
        return 2
    doc = json.loads(raw.decode("utf-8").replace("\r\n", "\n"))
    methods = Counter(e["method"] for e in doc["rows"])
    file_rows = methods.get("license-file", 0)
    hashed = sum(1 for r in doc["entries"] if r.get("licenseFileHash")) if "entries" in doc else 0
    prose = next((l for l in doc.get("limits", []) if re.search(r"rows were confirmed", l)), None)
    stated = None
    if prose:
        m = re.search(r"Only (\w+|\d+) rows", prose)
        words = {"one": 1, "two": 2, "three": 3, "four": 4, "five": 5, "six": 6, "seven": 7,
                 "eight": 8, "nine": 9, "ten": 10, "eleven": 11, "twelve": 12}
        stated = words.get(m.group(1).lower(), None) if m and m.group(1).isalpha() else int(m.group(1))
    print(f"revision={rev}")
    print(f"  prose claims   : {stated!r} rows confirmed by opening the file")
    print(f"                   sentence: {(prose or '')[:120]}")
    print(f"  its own data   : method=license-file on {file_rows} of {len(doc['rows'])} entries")
    print(f"  file hashes    : {hashed} rows carry licenseFileHash")
    if stated is None:
        print("VERDICT NO_PROSE_COUNT — the sentence is gone; nothing to contradict")
        return 0
    if stated == file_rows:
        print("VERDICT AGREES — the historical text matches its own data")
        return 0
    print(f"VERDICT CONTRADICTS — prose says {stated}, the document's own method fields say {file_rows}")
    return 1


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    raise SystemExit(main())

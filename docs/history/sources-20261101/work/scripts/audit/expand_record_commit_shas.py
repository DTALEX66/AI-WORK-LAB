"""Expand abbreviated commit fields in the error ledger to full 40-hex SHAs, or say why not.

    python scripts/audit/expand_record_commit_shas.py            # report only
    python scripts/audit/expand_record_commit_shas.py --apply    # rewrite the ledger
    python scripts/audit/expand_record_commit_shas.py --check    # fail if any field is still abbreviated

An abbreviation is a pointer that only resolves inside one object database and grows ambiguous as the
repository grows; `stamp_record_verification.py` and the binding tool write full SHAs, so a hand-typed
`8157484` in the same field is a different kind of claim from a machine-written one. Both forms are
accepted by the ledger verifier today, which is how 85 of them accumulated.

Fields that do not resolve to a commit in this repository are LEFT ALONE and reported: some records
cite a commit that lives on another branch or another project's tree, and inventing a SHA for those
would be the worse error.
"""

from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
LEDGER = REPO / "taskpacks" / "current" / "error-ledger.json"
COMMIT_FIELDS = ("introducedCommit", "fixedCommit", "verifiedCommit")
FULL = re.compile(r"^[0-9a-f]{40}$")
ABBREV = re.compile(r"^[0-9a-f]{7,39}$")


def resolve(token: str) -> str | None:
    proc = subprocess.run(["git", "rev-parse", "--verify", "--quiet", f"{token}^{{commit}}"],
                          cwd=REPO, capture_output=True, text=True, encoding="utf-8", errors="replace")
    sha = proc.stdout.strip()
    return sha if proc.returncode == 0 and FULL.match(sha) else None


def audit(doc: dict) -> tuple[list[dict], list[dict], list[dict]]:
    """(already_full, expandable, unresolvable)"""
    full, expandable, unresolved = [], [], []
    for record in doc["errors"]:
        lifecycle = record.get("lifecycle") or {}
        for field in COMMIT_FIELDS:
            value = lifecycle.get(field)
            if not isinstance(value, str) or not value.strip():
                continue
            entry = {"errorId": record["error_id"], "field": field, "value": value}
            if FULL.match(value):
                full.append(entry)
            elif ABBREV.match(value):
                target = resolve(value)
                if target:
                    expandable.append({**entry, "expanded": target})
                else:
                    unresolved.append(entry)
            else:
                unresolved.append(entry)
    return full, expandable, unresolved


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--apply", action="store_true")
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args()

    doc = json.loads(LEDGER.read_text(encoding="utf-8"))
    full, expandable, unresolved = audit(doc)
    print(f"COMMIT_SHA_AUDIT full={len(full)} expandable={len(expandable)} "
          f"unresolvable={len(unresolved)}")
    for item in expandable[:12]:
        print(f"  expand {item['errorId']}.{item['field']}: {item['value']} -> {item['expanded'][:12]}...")
    for item in unresolved[:12]:
        print(f"  KEEP {item['errorId']}.{item['field']}: {item['value']!r} does not resolve here")

    if args.check:
        if expandable or unresolved:
            print(f"COMMIT_SHA_CHECK_FAIL abbreviations={len(expandable)} "
                  f"unresolved={len(unresolved)}")
            return 1
        print(f"COMMIT_SHA_CHECK_PASS full={len(full)}")
        return 0

    if not args.apply:
        return 0

    by_id = {r["error_id"]: r for r in doc["errors"]}
    for item in expandable:
        by_id[item["errorId"]]["lifecycle"][item["field"]] = item["expanded"]
    LEDGER.write_text(json.dumps(doc, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")

    after = json.loads(LEDGER.read_text(encoding="utf-8"))
    full_now, expandable_now, unresolved_now = audit(after)
    if expandable_now:
        print(f"COMMIT_SHA_APPLY_INCOMPLETE still expandable={len(expandable_now)}")
        return 1
    print(f"COMMIT_SHA_APPLY_OK rewritten={len(expandable)} full={len(full_now)} "
          f"kept_unresolved={len(unresolved_now)} readback_verified")
    return 0


if __name__ == "__main__":
    sys.exit(main())

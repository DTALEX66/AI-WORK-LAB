#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""DLDS-G000 / DLDS-D010 / DL-AUDIT-20260914-05 — vendor source-lock identity gate.

Trace every entry of ``vendor/sources.lock.json`` (46) and grade its identity:

* an actually-enabled production donor MUST carry canonical URL + exact
  revision + content digest + license evidence. Missing any one of the four
  makes the entry FAIL-CLOSED for activation — the gate refuses to treat it as
  a usable identity and the workflow that would enable it must stop;
* entries whose recorded path no longer exists in the repository and which
  carry no canonical URL are UNRESOLVED: they are marked INERT (execution
  forbidden) instead of having a commit invented for them;
* the 39/46 URL and 0/46 revision debts are reported entry by entry, so the
  debt is a recorded ledger, not a silent gap.

The gate is deterministic and read-only: it never writes into the lock file
and never performs network access. A digest of a vendored copy is computed
locally only when the copy actually exists in the repository; an upstream
revision is never guessed.

Usage:
    python scripts/verify_source_lock.py            # evaluate + print report
    python scripts/verify_source_lock.py --check    # CI: exit non-zero on any
                                                     # enabled-with-missing-identity
"""
from __future__ import annotations

import argparse
import hashlib
import json
import re
import subprocess
from datetime import datetime, timezone
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
LOCK = "vendor/sources.lock.json"
REPORT = REPO / ".project-local/task-artifacts/source-lock/SOURCE-LOCK-IDENTITY-REPORT.json"
TASK_KEY = "DL-TP-20260914-DEEPSEEK-AUTHORITY-R1::DLDS-G000"
SHA256 = re.compile(r"^sha256:[0-9a-f]{64}$")
# A disposition that would mean the source is in active production identity.
ENABLED_DISPOSITIONS = {"ENABLED", "ACTIVE", "IN_USE", "PRODUCTION", "RELEASED"}
# The dispositions this lock actually uses: all are pre-activation.
PRE_ACTIVATION = {"LOCK_REFERENCE", "CONDITIONAL_POC", "ABSORB_MINIMAL"}
KNOWN_DISPOSITIONS = PRE_ACTIVATION | ENABLED_DISPOSITIONS


def load_lock() -> dict:
    document = json.loads((REPO / LOCK).read_text(encoding="utf-8"))
    if document.get("schemaVersion") != "design-lab/vendor-sources-lock/v1":
        raise SystemExit(f"unsupported lock schemaVersion: {document.get('schemaVersion')!r}")
    return document


def revision_of(entry: dict) -> str:
    for key in ("revision", "commit", "sha", "version"):
        value = entry.get(key)
        if value and value not in ("unknown", "latest"):
            return str(value)
    return ""


def digest_of(entry: dict) -> str:
    for key in ("digest", "contentHash", "sha256", "contentDigest"):
        value = entry.get(key)
        if value and value not in ("unknown",):
            return str(value)
    return ""


def vendored_digest(entry: dict) -> tuple[str, str]:
    """SHA-256 manifest over the vendored copy, when it exists locally.

    Returns (digest_or_empty, origin). This proves which bytes the repository
    actually holds; it does NOT supply an upstream revision, which stays a
    recorded debt.
    """
    path = REPO / entry.get("path", "")
    if not path.exists():
        return "", ""
    acc = hashlib.sha256()
    if path.is_file():
        acc.update(path.read_bytes())
        return "sha256:" + acc.hexdigest(), "vendored-copy:" + entry["path"]
    for file in sorted(path.rglob("*")):
        if file.is_file():
            acc.update(str(file.relative_to(path)).encode("utf-8"))
            acc.update(file.read_bytes())
    return "sha256:" + acc.hexdigest(), "vendored-copy:" + entry["path"]


def git_head() -> str:
    result = subprocess.run(["git", "-C", str(REPO), "rev-parse", "HEAD"],
                            capture_output=True, text=True, encoding="utf-8", errors="replace")
    return result.stdout.strip()


def evaluate() -> dict:
    lock = load_lock()
    entries = lock.get("sources", [])
    graded, failures, debts = [], [], []
    for entry in entries:
        source_id = entry.get("id", "?")
        disposition = entry.get("disposition", "")
        url = entry.get("canonicalUrl") or entry.get("url") or ""
        revision = revision_of(entry)
        digest = digest_of(entry)
        observed, digest_origin = vendored_digest(entry)
        license_ = entry.get("license") or entry.get("licence") or ""
        path_exists = (REPO / entry.get("path", "")).exists()

        fields = {
            "url": bool(url), "revision": bool(revision),
            "digest": bool(digest) or bool(observed), "license": bool(license_),
        }
        # An entry that is INERT (unrecoverable) may not be the identity of any
        # active flow; the gate only forbids *activation* of under-identified
        # sources. It must not block unrelated M1 work on historical material.
        inert = not path_exists and not url
        unresolvable = path_exists and not url and not inert and disposition == "LOCK_REFERENCE"
        enabled = disposition in ENABLED_DISPOSITIONS
        if enabled and not all(fields.values()):
            field_map = {k: "Y" if v else "N" for k, v in fields.items()}
            failures.append(
                f"{source_id}: disposition={disposition} but missing identity fields "
                f"{field_map}; activation refused")
        state = "UNRESOLVED_INERT" if inert else ("UNRESOLVED" if unresolvable
                                                   else ("IDENTITY_COMPLETE" if all(fields.values())
                                                         else "IDENTITY_DEBT"))
        graded.append({
            "id": source_id, "disposition": disposition, "state": state,
            "url": url or None, "revision": revision or None,
            "declared_digest": digest or None,
            "observed_vendored_digest": observed or None,
            "digest_origin": digest_origin or None,
            "license": license_ or None, "path_exists": path_exists,
        })
        if state in ("IDENTITY_DEBT", "UNRESOLVED"):
            missing = [k for k, present in fields.items() if not present]
            debts.append({"id": source_id, "state": state, "missing": missing,
                          "note": "execution forbidden until the listed identity fields are "
                                  "supplied from a source actually observed; no revision or "
                                  "commit is invented"})
    url_count = sum(1 for g in graded if g["url"])
    revision_count = sum(1 for g in graded if g["revision"])
    digest_count = sum(1 for g in graded if g["declared_digest"] or g["observed_vendored_digest"])
    return {
        "schemaVersion": "design-lab/source-lock-identity/v1",
        "task_key": TASK_KEY,
        "lock_file": LOCK,
        "subject_sha": git_head(),
        "generated_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "totals": {"entries": len(graded), "url": url_count, "revision": revision_count,
                   "digest": digest_count, "license": sum(1 for g in graded if g["license"])},
        "coverage_debt": [
            {"field": "url", "have": f"{url_count}/{len(graded)}",
             "note": "entries without a canonical URL cannot be re-acquired; kept as reference only"},
            {"field": "revision", "have": f"{revision_count}/{len(graded)}",
             "note": "no entry pins an upstream revision; activation requires one, recorded per entry"},
            {"field": "digest", "have": f"{digest_count}/{len(graded)}",
             "note": "declared digests, or locally computed vendored-copy digests; observed, not guessed"},
        ],
        "failures": failures,
        "debt_entries": debts,
        "graded": graded,
        "inert_rule": "an INERT/UNRESOLVED entry may never be promoted to an enabled "
                       "identity by a chat summary or a memory note; promotion requires a "
                       "lock-file amendment with all four identity fields",
        "verdict": "PASS" if not failures else "FAIL",
        "meaning": "a PASS means no source is enabled while under-identified; it does not "
                   "mean the debt is cleared, and it does not block unrelated M1 work",
    }


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check", action="store_true",
                        help="CI mode: evaluate and exit non-zero on any failure, write nothing")
    args = parser.parse_args(argv)
    document = evaluate()
    if not args.check:
        REPORT.parent.mkdir(parents=True, exist_ok=True)
        REPORT.write_text(json.dumps(document, indent=2, ensure_ascii=False) + "\n",
                          encoding="utf-8", newline="\n")
        print(f"SOURCE_LOCK_REPORT={REPORT.relative_to(REPO)}")
    t = document["totals"]
    print(f"SOURCE_LOCK={document['verdict']} entries={t['entries']} "
          f"url={t['url']}/{t['entries']} revision={t['revision']}/{t['entries']} "
          f"digest={t['digest']}/{t['entries']} license={t['license']}/{t['entries']} "
          f"debt={len(document['debt_entries'])} failures={len(document['failures'])}")
    for failure in document["failures"]:
        print("FAIL:", failure)
    return 0 if document["verdict"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())

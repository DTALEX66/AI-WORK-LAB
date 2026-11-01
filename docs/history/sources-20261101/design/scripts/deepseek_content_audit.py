#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""DLDS-D010 / DLDS-D040 — third-party source audit and duplicate content audit.

D010: every third-party project that lives in this repository must be either a
minimal absorption with a stated licence or a lock reference with a canonical
URL, revision, hash, licence and disposition. This checks the lock against
reality: an entry whose path no longer exists is a stale claim, and an absorbed
tree that has no lock entry is an unaudited claim.

D040: duplicate content costs bytes and creates two places to update. Duplicates
are reported with their exact digests and a classification; nothing is deleted
here, because removing a referenced evidence path is a contract change.

Writes:
    reports/current/THIRD-PARTY-SOURCE-AUDIT.json
    reports/current/DUPLICATE-CONTENT-AUDIT.json
"""
from __future__ import annotations

import argparse
import hashlib
import json
import re
import subprocess
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
OUT = REPO / "reports/current"
LOCK = "vendor/sources.lock.json"
TASK_KEYS = ["DL-TP-20260914-DEEPSEEK-AUTHORITY-R1::DLDS-D010",
             "DL-TP-20260914-DEEPSEEK-AUTHORITY-R1::DLDS-D040"]
LICENCE_NAMES = {"LICENSE", "LICENSE.md", "LICENSE.txt", "NOTICE", "COPYING", "SOURCE.md"}
MIN_DUPLICATE_BYTES = 65536


def tracked() -> list:
    return [line for line in subprocess.run(["git", "-C", str(REPO), "ls-files"], capture_output=True,
                                            text=True, encoding="utf-8").stdout.splitlines()
            if line.strip()]


def git(*args: str) -> str:
    """One argv element per argument -- `git("rev-parse HEAD")` returns empty stdout."""
    return subprocess.run(["git", "-C", str(REPO), *args], capture_output=True, text=True,
                          encoding="utf-8", errors="replace").stdout.strip()


def provenance() -> dict:
    """The block the committed records carry and the generator did not.

    Measured 2026-10-09: `reports/current/THIRD-PARTY-SOURCE-AUDIT.json` and
    `DUPLICATE-CONTENT-AUDIT.json` carry `subjectSha` (042ac635...), `generatedBy`, `projection` and
    `fresh`, none of which this file emits -- so the committed records could not be reproduced by
    their own generator, and the first republish would have silently dropped a bound subject. The
    subject binding is what `verify_report_subject_binding.py` reads, so the generator has to own it.
    """
    return {
        "generatedBy": "scripts/deepseek_content_audit.py",
        "subjectSha": git("rev-parse", "HEAD"),
        "projection": True,
        "fresh": False,
        "provenanceMeaning": "subjectSha is HEAD at the end of the run that computed this audit; "
                             "fresh=false says a generation timestamp is not a test time, and this "
                             "record is a projection over tracked files, not an execution",
    }


#: A lock entry whose path is DECLARED to live in the gitignored local cache.
#: Absence there is a statement about this machine, not about the repository.
_DECLARED_CACHE_PREFIXES = re.compile(r"^\.project-local/(cache|run|tmp)/")


def third_party_audit(files: list) -> dict:
    lock_path = REPO / LOCK
    lock = json.loads(lock_path.read_text(encoding="utf-8")) if lock_path.is_file() else {}
    entries = []
    for source in lock.get("sources", []):
        path = source.get("path", "")
        target = REPO / path
        tracked_here = sum(1 for f in files if f == path or f.startswith(path.rstrip("/") + "/"))
        on_disk = target.exists()
        disposition = source.get("disposition")
        if tracked_here:
            status = "PRESENT"
        elif on_disk:
            status = "FULL_COPY_IN_IGNORED_CACHE"
        elif disposition == "LOCK_REFERENCE":
            # LOCK_REFERENCE means the full copy was deliberately removed and only
            # the reference remains (verify_knowledge_lifecycle.py documents this).
            status = "CORRECT_LOCK_REFERENCE"
        elif _DECLARED_CACHE_PREFIXES.match(path):
            # G, fourth instance (owner 2026-10-12): 37 of the 46 lock entries declare a
            # path under .project-local/cache/vendor/ -- a gitignored cache that exists only
            # on a machine which fetched it. This audit used to call their absence
            # MISSING_ABSORBED_TREE and flip the verdict, so the stored record could only
            # ever be true on the one machine that had the cache: CI read
            # "absorbed tree missing" where the owner reads "cached copy present".
            #
            # That is a machine fact masquerading as a repository verdict. A declared
            # CACHE path being absent is NOT a defect; an IN-REPO declared path being
            # absent still is, and still lands in `missing_absorbed_trees` below. The
            # status is named, not hidden -- CACHE_ABSENT is visibly different from
            # FULL_COPY_IN_IGNORED_CACHE, so "this machine has not fetched it" never reads
            # as "the repository is missing it".
            status = "CACHE_ABSENT"
        else:
            status = "MISSING_ABSORBED_TREE"
        entries.append({
            "id": source.get("id"),
            "path": path,
            "disposition": disposition,
            "license": source.get("license"),
            "declared_files": source.get("files"),
            "tracked_files_now": tracked_here,
            "on_disk": on_disk,
            "status": status,
            "has_revision": bool(source.get("commit") or source.get("revision") or source.get("hash")
                                 or source.get("pinnedRevision")),
            "has_url": bool(source.get("canonicalUrl") or source.get("canonical_url")
                            or source.get("url")),
            "canonical_url": source.get("canonicalUrl") or source.get("canonical_url") or source.get("url"),
            "provenance_source": source.get("provenanceSource"),
        })
    present = [e for e in entries if e["status"] == "PRESENT"]
    cached = [e for e in entries if e["status"] == "FULL_COPY_IN_IGNORED_CACHE"]
    cache_absent = [e for e in entries if e["status"] == "CACHE_ABSENT"]
    references = [e for e in entries if e["status"] == "CORRECT_LOCK_REFERENCE"]
    missing = [e for e in entries if e["status"] == "MISSING_ABSORBED_TREE"]
    unidentified = [e for e in entries if not e["has_revision"] or not e["has_url"]]
    # Absorbed trees: a directory that carries its own licence/attribution file.
    markers = defaultdict(list)
    for rel in files:
        if Path(rel).name in LICENCE_NAMES and "/" in rel:
            markers[str(Path(rel).parent).replace("\\", "/")].append(Path(rel).name)
    locked_dirs = {e["path"].rstrip("/") for e in entries}
    absorbed = []
    for directory, names in sorted(markers.items()):
        absorbed.append({
            "directory": directory,
            "markers": sorted(names),
            "tracked_files": sum(1 for f in files if f.startswith(directory + "/")),
            "covered_by_lock": any(directory == locked or directory.startswith(locked + "/") or
                                   locked.startswith(directory + "/") for locked in locked_dirs),
        })
    uncovered = [a for a in absorbed if not a["covered_by_lock"]]
    return {
        "schemaVersion": "design-lab/third-party-source-audit/v1",
        "task_key": TASK_KEYS[0],
        **provenance(),
        "generated_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "lock": {"path": LOCK, "exists": lock_path.is_file(),
                 "schemaVersion": lock.get("schemaVersion"), "entries": len(entries)},
        "entries": entries,
        "counts": {"entries": len(entries), "present": len(present),
                   "full_copy_in_ignored_cache": len(cached),
                   # Machine-local by construction: this count is expected to differ
                   # between a workstation that fetched the caches and a clean clone.
                   "declared_cache_absent": len(cache_absent),
                   "correct_lock_reference": len(references),
                   "missing_absorbed_tree": len(missing),
                   "with_canonical_url": sum(1 for e in entries if e["has_url"]),
                   "without_canonical_url": sum(1 for e in entries if not e["has_url"]),
                   "with_pinned_revision": sum(1 for e in entries if e["has_revision"]),
                   "without_pinned_revision": sum(1 for e in entries if not e["has_revision"]),
                   "without_revision_or_url": len(unidentified),
                   "absorbed_trees_with_own_licence": len(absorbed),
                   "absorbed_trees_not_in_lock": len(uncovered)},
        "findings": {
            "without_canonical_url": [e["id"] for e in entries if not e["has_url"]],
            "without_pinned_revision": [e["id"] for e in entries if not e["has_revision"]],
            # Defect list only: CACHE_ABSENT entries are deliberately NOT here, because
            # their absence is a property of the machine, not of the repository.
            "missing_absorbed_trees": [{"id": e["id"], "path": e["path"]} for e in missing],
            "declared_cache_absent": [{"id": e["id"], "path": e["path"]}
                                        for e in cache_absent],
            "absorbed_trees_outside_lock": [a["directory"] for a in uncovered],
        },
        "verdict": ("NO_FULL_THIRD_PARTY_SOURCE_TREES_TRACKED" if not uncovered and not missing
                    else "REVIEW_ABSORBED_TREES_OUTSIDE_LOCK"),
        "note": "LOCK_REFERENCE with no in-repo copy is the intended state, not a stale claim: the "
                "full copy was removed and only the reference remains. A CONDITIONAL_POC or "
                "ABSORB_MINIMAL entry whose IN-REPO path is gone is a real defect and is "
                "listed under missing_absorbed_trees. An entry whose path is DECLARED under "
                "the gitignored local cache and is absent on this machine is reported as "
                "CACHE_ABSENT: that says this machine never fetched it, which is not a "
                "repository defect and must not move the verdict.",
    }


def duplicate_audit(files: list) -> dict:
    groups = defaultdict(list)
    for rel in files:
        path = REPO / rel
        try:
            size = path.stat().st_size
            if size < MIN_DUPLICATE_BYTES:
                continue
            digest = hashlib.sha256(path.read_bytes()).hexdigest()
        except OSError:
            continue
        groups[digest].append({"path": rel, "bytes": size})
    duplicates = []
    for digest, members in groups.items():
        if len(members) < 2:
            continue
        directories = {str(Path(m["path"]).parent) for m in members}
        fixtures = all(m["path"].startswith(("fixtures/", "reports/history/")) for m in members)
        duplicates.append({
            "sha256": digest,
            "bytes_each": members[0]["bytes"],
            "wasted_bytes": members[0]["bytes"] * (len(members) - 1),
            "members": [m["path"] for m in members],
            "directories": sorted(directories),
            "classification": ("FIXTURE_OR_HISTORICAL_DUPLICATE" if fixtures
                               else "EVIDENCE_DUPLICATE_ACROSS_ADAPTER_DIRS"),
            "recommendation": ("keep: the copy is part of a self-contained fixture or a differently "
                               "named historical record" if fixtures else
                               "consolidate only by editing the owning adapter manifest in the same "
                               "change; an evidence path is a contract, not a file layout"),
        })
    duplicates.sort(key=lambda d: -d["wasted_bytes"])
    return {
        "schemaVersion": "design-lab/duplicate-content-audit/v1",
        "task_key": TASK_KEYS[1],
        **provenance(),
        "generated_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "threshold_bytes": MIN_DUPLICATE_BYTES,
        "groups": duplicates,
        "counts": {"groups": len(duplicates),
                   "wasted_bytes": sum(d["wasted_bytes"] for d in duplicates),
                   "wasted_mib": round(sum(d["wasted_bytes"] for d in duplicates) / 1048576, 3)},
        "policy": "duplicate removal is a contract change whenever a manifest references the path; "
                  "this audit reports, it does not delete",
    }


def judgement(third: dict, duplicates: dict, load=None) -> tuple:
    """Compare the two records against what the tree says now, and split defect from churn.

    The record's own note separates the kinds of list it publishes: an absorbed tree that is missing
    or outside the lock is a defect, while a source with no canonical URL or pinned revision is
    declared debt (37 of 46 entries are local-cache-only today and the owner has not ruled on pinning
    them). So one direction fails and the other is reported. Counts and duplicate groups move with
    every commit -- pinning them would demand a writer run per commit, which is the disease this
    branch exists to avoid, and comparing them against a clone's file list would only restate the
    tree. `load` is a seam so a test can plant a stored-side value without touching a tracked file.
    """
    if load is None:
        def load(name):
            path = OUT / name
            return json.loads(path.read_text(encoding="utf-8")) if path.is_file() else None
    failures, notices = [], []
    for name, payload, constants, defect_keys in (
            ("THIRD-PARTY-SOURCE-AUDIT.json", third,
             ("schemaVersion", "task_key"), ("absorbed_trees_outside_lock",
                                             "missing_absorbed_trees")),
            ("DUPLICATE-CONTENT-AUDIT.json", duplicates,
             ("schemaVersion", "task_key", "threshold_bytes", "policy"), ())):
        stored = load(name)
        if stored is None:
            failures.append(f"CONTENT-AUDIT-RECORD-MISSING {name}")
            continue
        for field in constants:
            if stored.get(field) != payload.get(field):
                failures.append(f"CONTENT-AUDIT-CONTRACT {name}.{field} stored="
                                f"{stored.get(field)!r} recomputed={payload.get(field)!r}")
        for field in ("generatedBy", "subjectSha", "projection", "fresh"):
            if field not in stored:
                failures.append(f"CONTENT-AUDIT-NO-PROVENANCE {name} carries no {field}, so the "
                                "record cannot say what it was computed against")
        subject = str(stored.get("subjectSha") or "")
        if subject and not re.fullmatch(r"[0-9a-f]{40}", subject):
            failures.append(f"CONTENT-AUDIT-SUBJECT {name}.subjectSha={subject!r} names no commit")
        if stored.get("lock", {}).get("path") != payload.get("lock", {}).get("path"):
            failures.append(f"CONTENT-AUDIT-CONTRACT {name} audits a different lock than the record")
        if "verdict" in stored and stored.get("verdict") != payload.get("verdict"):
            failures.append(f"CONTENT-AUDIT-VERDICT {name} stored={stored.get('verdict')!r} "
                            f"recomputed={payload.get('verdict')!r}")
        for key in defect_keys:
            grew = sorted({str(x) for x in payload["findings"].get(key) or []}
                          - {str(x) for x in stored["findings"].get(key) or []})
            if grew:
                failures.append(f"CONTENT-AUDIT-DEFECT {name}.findings.{key} gained {grew}")
        if stored.get("counts") != payload.get("counts"):
            notices.append(f"{name} counts moved stored="
                           f"{json.dumps(stored.get('counts'), sort_keys=True)} recomputed="
                           f"{json.dumps(payload.get('counts'), sort_keys=True)}")
        for key in ("without_canonical_url", "without_pinned_revision"):
            if key not in stored.get("findings", {}):
                continue
            paid = sorted({str(x) for x in stored["findings"].get(key) or []}
                          - {str(x) for x in payload["findings"].get(key) or []})
            added = sorted({str(x) for x in payload["findings"].get(key) or []}
                           - {str(x) for x in stored["findings"].get(key) or []})
            if paid or added:
                notices.append(f"{name}.findings.{key} paid={paid or 'none'} new={added or 'none'}")
        if "groups" in stored and len(stored["groups"]) != len(payload["groups"]):
            notices.append(f"{name} groups stored={len(stored['groups'])} "
                           f"recomputed={len(payload['groups'])} (the audit reports, it does not delete)")
    return failures, notices


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args(argv)
    files = tracked()
    third = third_party_audit(files)
    duplicates = duplicate_audit(files)
    if args.check:
        failures, notices = judgement(third, duplicates)
        for failure in failures:
            print("CONTENT_AUDIT=FAIL " + failure)
        for notice in notices:
            print("CONTENT_AUDIT=NOTICE " + notice)
        print(f"CONTENT_AUDIT={'PASS' if not failures else 'FAIL'} records=2 findings={len(failures)} "
              f"notices={len(notices)}")
        return 0 if not failures else 1
    OUT.mkdir(parents=True, exist_ok=True)
    for name, payload in (("THIRD-PARTY-SOURCE-AUDIT.json", third),
                          ("DUPLICATE-CONTENT-AUDIT.json", duplicates)):
        (OUT / name).write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n",
                                encoding="utf-8", newline="\n")
        print(f"wrote reports/current/{name}")
    print("third-party:", third["counts"], "|", third["verdict"])
    print("duplicates:", duplicates["counts"])
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

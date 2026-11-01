#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""DLDS-E020 / E030 / E040 — migrate DESIGN-LAB's own legacy `.hermes` runtime.

What this does: copies the objects the spill census proved are DESIGN-LAB's own
(from `.hermes/task-runtime/**` and `.hermes/task-artifacts/**`) into
``.project-local/archive/hermes-legacy/``, verifies the copy by directory digest,
writes a delete manifest with a restore command, and only then removes the
originals.

What this refuses: anything not provably written by DESIGN-LAB. Hermes-native
session history, personal memory, credentials and other projects are never
listed for migration, never copied and never deleted — `skill-call-index.json` is
the live example and stays marked DO_NOT_TOUCH.

The taskpack's migration recipe is copy -> hash compare -> update pointer ->
readback -> restart/reopen test -> quarantine old -> delete. There is no active
reader of these paths (`DLDS-B020` found zero active code references), so the
readback is the digest comparison and the "restart/reopen" step is recorded as
not applicable with that evidence.

Usage:
    python scripts/deepseek_hermes_migration.py --plan
    python scripts/deepseek_hermes_migration.py --apply
    python scripts/deepseek_hermes_migration.py --verify
    python scripts/deepseek_hermes_migration.py --restore

`--verify` is the read-only form and it is split (2026-10-09): the manifest it audits is the
versioned copy inside the preserved evidence bundle (``docs/audits/DESIGN-LAB-UIKIT-CONFORMANCE-2026-09-28/session/hermes-legacy``), and an archived object
that is gone must be named by the versioned prune record, so a deletion without a tracked reason
still fails. Whether this machine still holds the archive is reported as
``archive=MEASURED_ON_THIS_MACHINE`` or ``ABSENT_ON_THIS_MACHINE``; a clean checkout is not a
deletion, and that is what previously made this form fail forever while nothing invoked it.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import re
import shutil
from datetime import datetime, timezone
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
CENSUS = REPO / "reports/current/SPILL-CENSUS.json"
ARCHIVE = REPO / ".project-local/archive/hermes-legacy"
MANIFEST = ARCHIVE / "MIGRATION-MANIFEST.json"
# Versioned copies of the two records the verdict needs: the migration manifest's tracked copy
# (sha256 prefix 5088e4766929b68f, equal to the live copy) and the prune manifest, tracked since
# 2026-09-26.
TRACKED_MANIFEST = REPO / "docs/audits/DESIGN-LAB-UIKIT-CONFORMANCE-2026-09-28/session/hermes-legacy/MIGRATION-MANIFEST.json"
PRUNE_RECORD = REPO / ("docs/audits/DESIGN-LAB-UIKIT-CONFORMANCE-2026-09-28/evidence/"
                       "governance-state/prune-manifest-2026-09-26.json")
ARCHIVE_PREFIX = "archive/hermes-legacy/"
DIGEST_FORM = re.compile(r"^(sha256:)?[0-9a-f]{64}$")
TASK_KEYS = ["DL-TP-20260914-DEEPSEEK-AUTHORITY-R1::DLDS-E020",
             "DL-TP-20260914-DEEPSEEK-AUTHORITY-R1::DLDS-E030",
             "DL-TP-20260914-DEEPSEEK-AUTHORITY-R1::DLDS-E040"]
LOOSE_SOURCES = (".hermes/task-runtime",)


def recorded_removals() -> dict:
    """Archive-relative targets whose deletion a tracked record already states.

    The prune manifest writes each entry as `<path> (<size>, <reason>)`; the path is everything
    before the first space, and the parenthetical is the reason, which must be there -- a removal
    without a stated reason is not a record, it is a disappearance.
    """
    if not PRUNE_RECORD.is_file():
        return {}
    document = json.loads(PRUNE_RECORD.read_text(encoding="utf-8"))
    removals = {}
    for entry in (document.get("phase2") or {}).get("removed") or []:
        path = str(entry).split(" ")[0].replace("\\", "/")
        reason = str(entry)[len(path):].strip()
        if not path.startswith(ARCHIVE_PREFIX):
            continue
        target = ".project-local/" + path
        removals[target] = {"reason": reason, "pruned_at": (document.get("phase2") or {}).get("at")
                            or document.get("pruned_at"), "entry": str(entry)}
    return removals


def manifest_findings(manifest: dict, records: list, removals: dict) -> list:
    """The tracked half: the two versioned records must describe the same set of objects."""
    findings = []
    if not str(manifest.get("schemaVersion") or "").startswith("design-lab/hermes-migration-manifest"):
        findings.append(f"schemaVersion={manifest.get('schemaVersion')!r} is not the migration "
                        "manifest contract")
    declared = set(manifest.get("task_keys") or [])
    if not declared <= set(TASK_KEYS):
        findings.append(f"task_keys={sorted(declared)} name operations outside "
                        f"{sorted(TASK_KEYS)}")
    if manifest.get("restore_command") != "python scripts/deepseek_hermes_migration.py --restore":
        findings.append("restore_command is not this tool's documented --restore form")
    seen = set()
    for record in records:
        source = str(record.get("source") or "")
        target = str(record.get("target") or "")
        label = target or source or "<unnamed record>"
        if not source.startswith(".hermes/"):
            findings.append(f"record {label} has a source outside the legacy roots: {source!r}")
        if not target.startswith(".project-local/archive/hermes-legacy/"):
            findings.append(f"record {label} archives outside the hermes-legacy root: {target!r}")
        if target in seen:
            findings.append(f"record {label} appears twice; one target cannot hold two datasets")
        seen.add(target)
        if not DIGEST_FORM.match(str(record.get("verified_digest") or "")):
            findings.append(f"record {label} has no digest a restore could be verified against: "
                            f"{record.get('verified_digest')!r}")
        restore = str(record.get("restore") or "")
        if not (restore.startswith("copy ") and "back to" in restore
                and Path(target).name in restore):
            findings.append(f"record {label} has a restore note that does not say where the "
                            f"bytes go back: {restore!r}")
        if int(record.get("files") or 0) <= 0 and int(record.get("bytes") or 0) <= 0 \
                and not record.get("empty"):
            findings.append(f"record {label} claims an archived object with neither files nor bytes")
    for target in removals:
        if target not in seen:
            findings.append(f"the prune record names {target} as an archived object it removed, "
                            "but no migration record describes that object")
    return findings



def digest_tree(path: Path) -> tuple:
    files = 0
    total = 0
    digest = hashlib.sha256()
    for item in sorted(path.rglob("*")):
        try:
            if not item.is_file():
                continue
            stat = item.stat()
        except OSError:
            continue
        files += 1
        total += stat.st_size
        digest.update(str(item.relative_to(path)).encode("utf-8"))
        digest.update(str(stat.st_size).encode("utf-8"))
    return files, total, "sha256:" + digest.hexdigest()


def objects(from_census: bool = True) -> list:
    """Migration targets: census entries owned by DESIGN-LAB with a target path."""
    if not CENSUS.is_file():
        raise SystemExit("run scripts/deepseek_spill_census.py first")
    census = json.loads(CENSUS.read_text(encoding="utf-8"))
    targets = []
    for item in census["repository_legacy_objects"]:
        if item["owner"] != "DESIGN-LAB" or not item.get("target_path"):
            continue
        targets.append({"source": item["source_path"], "target": item["target_path"],
                        "classification": item["classification"], "bytes": item["bytes"],
                        "digest": item["digest"], "empty": bool(item.get("empty"))})
    for rel_root in LOOSE_SOURCES:
        root = REPO / rel_root
        if not root.is_dir():
            continue
        for child in sorted(root.iterdir()):
            if child.is_dir():
                continue
            files, size, digest = digest_tree(child.parent) if False else (1, child.stat().st_size, None)
            targets.append({"source": str(child.relative_to(REPO)).replace("\\", "/"),
                            "target": f".project-local/archive/hermes-legacy/runtime/_loose/{child.name}",
                            "classification": "RUNTIME_STATE", "bytes": size, "digest": digest})
    return targets


def plan(targets: list) -> int:
    print(f"PLAN migrate {len(targets)} DESIGN-LAB-owned legacy objects into {ARCHIVE.relative_to(REPO)}")
    total = 0
    for item in targets:
        total += item["bytes"]
        print(f"  {item['classification']:14} {item['bytes'] / 1048576:7.3f} MiB  "
              f"{item['source']}  ->  {item['target']}")
    print(f"  total {total / 1048576:.2f} MiB; nothing has been moved")
    return 0


def apply(targets: list) -> int:
    ARCHIVE.mkdir(parents=True, exist_ok=True)
    records = []
    for item in targets:
        source = REPO / item["source"]
        target = REPO / item["target"]
        if not source.exists():
            print(f"  skip (absent): {item['source']}")
            continue
        target.parent.mkdir(parents=True, exist_ok=True)
        if item.get("empty"):
            # An empty legacy directory holds no bytes to hash: it is removed and
            # recorded rather than copied into the archive.
            shutil.rmtree(source, ignore_errors=True)
            records.append({**item, "files": 0, "bytes": 0, "verified_digest": None,
                            "restore": "nothing to restore: the directory was empty"})
            print(f"  removed empty legacy directory {item['source']}")
            continue
        if source.is_dir():
            if target.exists():
                shutil.rmtree(target)
            shutil.copytree(source, target)
            files, size, digest = digest_tree(target)
            source_files, source_size, source_digest = digest_tree(source)
            if digest != source_digest:
                raise SystemExit(f"DIGEST_MISMATCH after copy: {item['source']}")
            shutil.rmtree(source)
        else:
            shutil.copyfile(source, target)
            if target.read_bytes() != source.read_bytes():
                raise SystemExit(f"BYTE_MISMATCH after copy: {item['source']}")
            files, size = 1, target.stat().st_size
            digest = hashlib.sha256(target.read_bytes()).hexdigest()
            source.unlink()
        records.append({**item, "files": files, "bytes": size, "verified_digest": digest,
                        "restore": f"copy {item['target']} back to {item['source']}"})
        print(f"  migrated {item['source']} ({size / 1048576:.3f} MiB) verified")
    manifest = {
        "schemaVersion": "design-lab/hermes-migration-manifest/v1",
        "task_keys": TASK_KEYS,
        "migrated_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "recipe": "copy -> digest compare -> pointer check -> delete original",
        "pointer_update": "none required: DLDS-B020 found no active code reference to these paths; "
                          "the only tracked mention is a historical fixture string in "
                          "design-lab/evals/failures/failure-registry.json whose file "
                          "(.hermes/task-runtime/start_comfyui.py) is already absent",
        "restart_reopen_test": "not applicable: no reader exists for these legacy roots",
        "refused": [{"path": ".hermes/skill-call-index.json",
                     "reason": "not provably DESIGN-LAB's; agent-native artifact, DO_NOT_TOUCH"}],
        "restore_command": "python scripts/deepseek_hermes_migration.py --restore",
        "records": records,
    }
    # Merge instead of clobbering: a second apply must not erase the earlier run.
    if MANIFEST.is_file():
        previous = json.loads(MANIFEST.read_text(encoding="utf-8"))
        known = {record["source"] for record in records}
        merged = previous.get("records", []) and [r for r in previous["records"]
                                                  if r["source"] not in known] or []
        manifest["records"] = merged + records
        manifest["migrated_at"] = previous.get("migrated_at", manifest["migrated_at"])
        manifest["updated_at"] = datetime.now(timezone.utc).isoformat(timespec="seconds")
        manifest["runs"] = previous.get("runs", 1) + 1
    MANIFEST.write_text(json.dumps(manifest, indent=2, ensure_ascii=False) + "\n",
                        encoding="utf-8", newline="\n")
    print(f"MIGRATION=APPLIED objects={len(records)} "
          f"bytes={sum(r['bytes'] for r in records)} manifest={MANIFEST.relative_to(REPO)}")
    return 0


def reconcile() -> int:
    """Rebuild the manifest from the archive, so a lost manifest is recoverable."""
    if not ARCHIVE.is_dir():
        print("RECONCILE=FAIL no archive")
        return 1
    census = json.loads(CENSUS.read_text(encoding="utf-8")) if CENSUS.is_file() else {"repository_legacy_objects": []}
    by_name = {Path(item["source_path"]).name: item for item in census["repository_legacy_objects"]}
    records = []
    for bucket in ("runtime", "artifacts"):
        root = ARCHIVE / bucket
        if not root.is_dir():
            continue
        for child in sorted(root.iterdir()):
            if child.name == "_loose":
                for loose in sorted(child.iterdir()):
                    files, size = 1, loose.stat().st_size
                    digest = hashlib.sha256(loose.read_bytes()).hexdigest()
                    records.append({"source": f".hermes/task-{bucket}/{loose.name}",
                                    "target": str(loose.relative_to(REPO)).replace("\\", "/"),
                                    "classification": "RUNTIME_STATE", "files": files, "bytes": size,
                                    "verified_digest": digest,
                                    "restore": f"copy {loose.name} back to .hermes/task-{bucket}/"})
                continue
            files, size, digest = digest_tree(child)
            if files == 0:
                continue
            records.append({
                "source": (by_name.get(child.name, {}).get("source_path")
                           or f".hermes/task-{bucket}/{child.name}"),
                "target": str(child.relative_to(REPO)).replace("\\", "/"),
                "classification": by_name.get(child.name, {}).get("classification", "RUNTIME_STATE"),
                "files": files, "bytes": size, "verified_digest": digest,
                "restore": f"copy {child.name} back to .hermes/task-{bucket}/",
                "reconciled": True,
            })
    manifest = {"schemaVersion": "design-lab/hermes-migration-manifest/v1", "task_keys": TASK_KEYS,
                "migrated_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
                "reconciled_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
                "recipe": "rebuilt from the archive after a manifest was overwritten by a second apply",
                "restore_command": "python scripts/deepseek_hermes_migration.py --restore",
                "refused": [{"path": ".hermes/skill-call-index.json",
                             "reason": "agent-native artifact, DO_NOT_TOUCH"}],
                "records": records}
    MANIFEST.write_text(json.dumps(manifest, indent=2, ensure_ascii=False) + "\n",
                        encoding="utf-8", newline="\n")
    print(f"RECONCILE=OK records={len(records)} bytes={sum(r['bytes'] for r in records)}")
    return 0


def verify() -> int:
    """Two halves: what the tracked records say, and what this machine still holds.

    Measured 2026-10-09: this form had been FAIL for weeks with nobody watching, because it is
    invoked by no CI table, no aggregate entry and no test. Its complaint was real but stale --
    108 of 109 archived objects are present with unchanged digests, no source was left behind, and
    the single absent one (`.project-local/archive/hermes-legacy/runtime/dl-ad-pkg-ci`, 253.3 MB /
    5559 files) is removed in a tracked record: `prune-manifest-2026-09-26.json` `phase2.removed[0]`
    and the closeout ledger §C, both dated 2026-09-26, both stating it was CI-reproducible. So the
    assertion "an archived object must still be here" was never updated for a recorded, reasoned
    deletion, and the honest repair is to require the deletion to be *named* rather to pretend the
    archive is intact.

    The manifest is read from its archived copy under `reports/history/`, which is versioned; the
    live copy under the gitignored archive root is what makes the survival question machine-bound,
    so absence of that root is reported as `archive=ABSENT_ON_THIS_MACHINE` and never fails. An
    archived object that is missing WITHOUT a tracked removal record still fails.
    """
    if not TRACKED_MANIFEST.is_file():
        print("MIGRATION_VERIFY=FAIL no tracked manifest")
        return 1
    manifest = json.loads(TRACKED_MANIFEST.read_text(encoding="utf-8"))
    records = manifest["records"]
    removals = recorded_removals()
    findings = manifest_findings(manifest, records, removals)

    archive_present = ARCHIVE.is_dir()
    if archive_present:
        for record in records:
            target = REPO / record["target"]
            if record.get("empty"):
                if (REPO / record["source"]).exists():
                    findings.append(f"empty legacy directory still present {record['source']}")
                continue
            if not target.exists():
                if record["target"] in removals:
                    continue
                findings.append(f"missing target {record['target']} is not named by a tracked "
                                "removal record")
                continue
            if (REPO / record["source"]).exists():
                findings.append(f"source still present {record['source']}")
            if target.is_dir():
                _, _, digest = digest_tree(target)
            else:
                digest = hashlib.sha256(target.read_bytes()).hexdigest()
            if digest != record["verified_digest"]:
                findings.append(f"digest changed {record['target']}")

    for finding in findings:
        print("FAIL", finding)
    survival = ("ABSENT_ON_THIS_MACHINE" if not archive_present
                else "MEASURED_ON_THIS_MACHINE")
    print(f"MIGRATION_VERIFY={'PASS' if not findings else 'FAIL'} objects={len(records)} "
          f"recorded_removals={len(removals)} archive={survival}")
    return 0 if not findings else 1



def restore() -> int:
    if not MANIFEST.is_file():
        print("RESTORE=FAIL no manifest")
        return 1
    manifest = json.loads(MANIFEST.read_text(encoding="utf-8"))
    for record in manifest["records"]:
        source = REPO / record["target"]
        target = REPO / record["source"]
        if not source.exists():
            print("RESTORE_FAIL missing", record["target"])
            return 1
        target.parent.mkdir(parents=True, exist_ok=True)
        if source.is_dir():
            if target.exists():
                shutil.rmtree(target)
            shutil.copytree(source, target)
        else:
            shutil.copyfile(source, target)
        print("restored", record["source"])
    print("RESTORED: run the zero-spill probe and commit to complete the rollback")
    return 0


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--plan", action="store_true")
    group.add_argument("--apply", action="store_true")
    group.add_argument("--verify", action="store_true")
    group.add_argument("--reconcile", action="store_true")
    group.add_argument("--restore", action="store_true")
    args = parser.parse_args(argv)
    if args.verify:
        return verify()
    if args.reconcile:
        return reconcile()
    if args.restore:
        return restore()
    targets = objects()
    return plan(targets) if args.plan else apply(targets)


if __name__ == "__main__":
    raise SystemExit(main())

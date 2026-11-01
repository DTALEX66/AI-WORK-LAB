#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""DLDS-E000 — spill data census.

Scope rules from the authority taskpack (section 27), applied literally:

* the DESIGN-LAB repository and ``.project-local`` may be inspected;
* agent homes (``~/.hermes``, ``~/.codex``, ``~/.dsh``) may be inspected **at
  path and metadata level only**, and only for entries that are identifiably
  DESIGN-LAB owned;
* private chat content, credentials, unrelated sessions and sibling projects are
  NOT read — this script never opens a file outside the repository tree;
* ``E:\\`` is never touched.

For every discovered object it records owner, size, hash (repository objects
only), source path, proposed target path, whether it is recreatable, and the
delete policy that applies.

Writes reports/current/SPILL-CENSUS.json.

`--check` judges the record; it does not re-census the disk. Measured 2026-10-09 in two trees of
`d6ba107f`: the old form compared `repository_totals_bytes` against a sum over `.hermes` children
that a clone does not have, so it printed PASS where the directories exist and DRIFT in a clean
checkout of the same commit (stored `{"UNKNOWN": 13638}` against `{}` with `.hermes/` ABSENT). At
the same time it passed in the generating tree while three of the agent-home counts it carries were
already stale there (`.codex` entries 83 recorded against 91 live, `.dsh` 0 against 9, `.hermes` 3
against 0) -- a field nobody compares is decoration, and a byte census nobody can reproduce is a
statement about one workstation.

So the check now asserts what is true of the record itself and of the repository: the path rules
still produce the recorded classification, reason, delete policy and recreatability; the totals
arithmetic adds up over the recorded objects; no two objects claim the same archive target; nothing
owner-marked UNPROVEN is proposed for touch; the spill premise holds, i.e. every recorded source
path is un-versioned content; and the privacy invariants the scope declares (agent homes visited at
path level only, `content_read` false, E: never touched). The live census is then reported --
`local_state=MATCHES_RECORDED_TOTALS / DIFFERS_FROM_RECORDED_TOTALS / NOTHING_ON_THIS_MACHINE` --
so drift on a machine that has the directories stays visible without being able to convict a
machine that has none.

Usage:
    python scripts/deepseek_spill_census.py [--check]
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import subprocess
from datetime import datetime, timezone
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
OUT = REPO / "reports/current/SPILL-CENSUS.json"
TASK_KEY = "DL-TP-20260914-DEEPSEEK-AUTHORITY-R1::DLDS-E000"
HOME = Path(os.environ.get("USERPROFILE", Path.home()))
# Agent homes are visited at path level only. Native state is never read.
AGENT_HOMES = {".hermes": "Hermes", ".codex": "Codex", ".dsh": "DSH"}
# Repository-side legacy roots that DESIGN-LAB itself used to write.
REPO_LEGACY_ROOTS = (".hermes/task-runtime", ".hermes/task-artifacts", ".hermes/task-runs")
# Names that belong to the agent, not to DESIGN-LAB, and are never touched.
AGENT_NATIVE_NAMES = {"sessions", "session", "memories", "memory", "credentials", "credentials.yaml",
                      ".credentials.yaml", ".env", "config.yaml", "settings.yaml", "auth.json",
                      "attachments", "browser", "log", "logs", "archived_sessions", "profiles",
                      "storages", "task-board", "desktop-plugins", "skin-center", "computer-use",
                      "dictation-history", "generated_images", "marketplaces", "automations",
                      "skill-call-index.json"}
DESIGN_LAB_MARKERS = ("design-lab", "design_lab", "designlab")


def git(*args: str) -> str:
    return subprocess.run(["git", "-C", str(REPO), *args], capture_output=True, text=True,
                          encoding="utf-8", errors="replace").stdout


def measure(path: Path) -> tuple:
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


def classify(rel: str) -> tuple:
    lowered = rel.lower()
    if "task-artifacts" in lowered or "evidence" in lowered or "task-artifacts" in lowered:
        return "EVIDENCE", "evidence output written by a DESIGN-LAB run"
    if "task-runtime" in lowered or "/runs/" in lowered or "runs/" in lowered:
        return "RUNTIME_STATE", "runtime working data written by a DESIGN-LAB run"
    if "cache" in lowered:
        return "CACHE", "recreatable cache"
    if "tmp" in lowered or "temp" in lowered:
        return "TEMP", "recreatable temporary data"
    if lowered.endswith((".pack", ".whl", ".tar.gz")):
        return "THIRD_PARTY", "third-party distribution material"
    return "UNKNOWN", "no path rule matched; classify before any action"


def repo_legacy_census() -> list:
    objects = []
    for rel_root in REPO_LEGACY_ROOTS:
        root = REPO / rel_root
        if not root.is_dir():
            continue
        for child in sorted(root.iterdir()):
            if not child.is_dir():
                continue
            kind, reason = classify(f"{rel_root}/{child.name}")
            files, size, digest = measure(child)
            empty = files == 0
            if empty:
                reason = (f"{reason}; empty legacy directory left by an older test-isolation era "
                          f"(the namespace now resolves under .project-local)")
            # Keep the runtime/artifact split in the target path: both trees have
            # a child called "reconstruction", and a collision would merge two
            # different datasets.
            bucket = "runtime" if "task-runtime" in rel_root else "artifacts"
            objects.append({
                "owner": "DESIGN-LAB",
                "classification": kind,
                "reason": reason,
                "empty": empty,
                "source_path": str(child.relative_to(REPO)).replace("\\", "/"),
                "target_path": f".project-local/archive/hermes-legacy/{bucket}/{child.name}",
                "files": files,
                "bytes": size,
                "digest": digest,
                "recreatable": kind in {"CACHE", "TEMP"} or empty,
                "delete_policy": ("REMOVE_EMPTY_LEGACY_DIRECTORY" if empty else
                                  "AUTO_WITH_MANIFEST" if kind in {"CACHE", "TEMP", "RUNTIME_STATE",
                                                                   "EVIDENCE"}
                                  else "OWNER_DELETE_APPROVAL_REQUIRED"),
            })
    # Anything at the .hermes root that is not one of the DESIGN-LAB legacy roots.
    root = REPO / ".hermes"
    if root.is_dir():
        for child in sorted(root.iterdir()):
            name = child.name
            if f".hermes/{name}" in REPO_LEGACY_ROOTS or name in {"task-runtime", "task-artifacts"}:
                continue
            size = child.stat().st_size if child.is_file() else measure(child)[1]
            objects.append({
                "owner": "UNPROVEN",
                "classification": "UNKNOWN",
                "reason": "not provably written by DESIGN-LAB; an agent-native artifact must not be "
                          "moved or deleted by this project",
                "source_path": f".hermes/{name}",
                "target_path": None,
                "files": 1 if child.is_file() else measure(child)[0],
                "bytes": size,
                "digest": None,
                "recreatable": False,
                "delete_policy": "DO_NOT_TOUCH",
            })
    return objects


def agent_home_discovery() -> dict:
    """Path-level only: list entries whose NAME identifies them as DESIGN-LAB owned."""
    discovery = {}
    for dirname, product in AGENT_HOMES.items():
        root = HOME / dirname
        entry = {"path": str(root), "exists": root.is_dir(), "product": product,
                 "content_read": False, "native_entries_seen": 0,
                 "design_lab_owned": [], "scope_note": "native sessions, memory, credentials and "
                                                       "unrelated projects are out of scope and unread"}
        if root.is_dir():
            try:
                for child in sorted(root.iterdir()):
                    entry["native_entries_seen"] += 1
                    if child.name in AGENT_NATIVE_NAMES:
                        continue
                    if any(marker in child.name.lower() for marker in DESIGN_LAB_MARKERS):
                        size = child.stat().st_size if child.is_file() else measure(child)[1]
                        entry["design_lab_owned"].append({
                            "name": child.name,
                            "kind": "file" if child.is_file() else "dir",
                            "bytes": size,
                        })
            except OSError as exc:
                entry["error"] = str(exc)
        discovery[dirname] = entry
    return discovery


def tracked_paths() -> set:
    result = subprocess.run(["git", "-C", str(REPO), "ls-files"], capture_output=True,
                            text=True, encoding="utf-8", errors="replace")
    return set((result.stdout or "").splitlines())


def implied_policy(classification: str, empty: bool) -> str:
    if empty:
        return "REMOVE_EMPTY_LEGACY_DIRECTORY"
    if classification in {"CACHE", "TEMP", "RUNTIME_STATE", "EVIDENCE"}:
        return "AUTO_WITH_MANIFEST"
    return "OWNER_DELETE_APPROVAL_REQUIRED"


def record_findings(record: dict) -> list:
    """Judge the census record against the rules that produced it and against git.

    Every finding here is answerable in any checkout of the commit, which is what the old
    byte-sum comparison never was.
    """
    findings: list[str] = []
    objects = record.get("repository_legacy_objects") or []
    tracked = tracked_paths()

    totals: dict = {}
    seen_targets: dict = {}
    for item in objects:
        source = str(item.get("source_path") or "")
        label = source or "<no source_path>"
        if not source:
            findings.append("SPILL-OBJECT-UNNAMED an object is recorded without a source path")
            continue
        if source.replace("\\", "/") in tracked:
            findings.append(f"SPILL-PREMISE-BROKEN {label} is recorded as spill but git versions "
                            "it, so this is repository content and must not be archived or deleted")
        if item.get("owner") == "UNPROVEN":
            if item.get("delete_policy") != "DO_NOT_TOUCH":
                findings.append(f"SPILL-UNPROVEN-TOUCHABLE {label} is not provably DESIGN-LAB "
                                f"content yet proposes {item.get('delete_policy')}")
            if item.get("target_path"):
                findings.append(f"SPILL-UNPROVEN-TARGET {label} would be moved by this project "
                                "even though its ownership is unproven")
            if not source.startswith(".hermes/"):
                findings.append(f"SPILL-UNPROVEN-SCOPE {label} is outside the repository legacy "
                                "roots this census is allowed to speak about")
            if item.get("recreatable"):
                findings.append(f"SPILL-UNPROVEN-RECREATABLE {label} claims an unproven object "
                                "can be recreated")
        else:
            kind, reason = classify(source)
            if item.get("classification") != kind:
                findings.append(f"SPILL-RULE-CLASSIFICATION {label} records "
                                f"{item.get('classification')!r}, the path rule says {kind!r}")
            if not str(item.get("reason") or "").startswith(reason):
                findings.append(f"SPILL-RULE-REASON {label} records a reason that does not start "
                                f"with the rule's own text {reason!r}")
            policy = implied_policy(str(item.get("classification") or ""), bool(item.get("empty")))
            if item.get("delete_policy") != policy:
                findings.append(f"SPILL-RULE-POLICY {label} records "
                                f"{item.get('delete_policy')!r}, the rule implies {policy!r}")
            recreatable = str(item.get("classification")) in {"CACHE", "TEMP"} or bool(item.get("empty"))
            if bool(item.get("recreatable")) != recreatable:
                findings.append(f"SPILL-RULE-RECREATABLE {label} records recreatable="
                                f"{item.get('recreatable')!r}, the rule implies {recreatable}")
            if not item.get("digest"):
                findings.append(f"SPILL-RULE-DIGEST {label} is a repository object with no digest, "
                                "so a restore cannot be verified")
        target = item.get("target_path")
        if target:
            if target in seen_targets:
                findings.append(f"SPILL-TARGET-COLLISION {target} is claimed by both "
                                f"{seen_targets[target]} and {label}; two different datasets would "
                                "be merged into one archive path")
            seen_targets[target] = label
        totals[str(item.get("classification"))] = (
            totals.get(str(item.get("classification")), 0) + int(item.get("bytes") or 0))

    if record.get("repository_totals_bytes") != totals:
        findings.append(f"SPILL-TOTALS-ARITHMETIC the record says "
                        f"{json.dumps(record.get('repository_totals_bytes'), sort_keys=True)} but "
                        f"its own objects sum to {json.dumps(totals, sort_keys=True)}")
    total_mib = round(sum(totals.values()) / 1048576, 2)
    if record.get("repository_total_mib") != total_mib:
        findings.append(f"SPILL-TOTALS-MIB the record says {record.get('repository_total_mib')!r}, "
                        f"the recorded bytes give {total_mib!r}")

    scope = record.get("scope") or {}
    if "E:\\" not in json.dumps(scope.get("never_touched") or []):
        findings.append("SPILL-SCOPE-E-DRIVE the census no longer declares E: untouched")
    if not scope.get("not_read"):
        findings.append("SPILL-SCOPE-NOT-READ the record no longer states what it refuses to read")
    homes = record.get("agent_homes") or {}
    if not homes:
        findings.append("SPILL-SCOPE-HOMES no agent homes were recorded, so the path-level-only "
                        "promise is not evidenced")
    for name, home in homes.items():
        if home.get("content_read"):
            findings.append(f"SPILL-PRIVACY {name} records content_read=true; native agent state "
                            "is out of scope and must never be read")
        if not home.get("scope_note"):
            findings.append(f"SPILL-PRIVACY {name} carries no scope note")
        if not isinstance(home.get("native_entries_seen"), int):
            findings.append(f"SPILL-SHAPE {name}.native_entries_seen is not a count")
    if str(record.get("verdict")) != "CENSUS_COMPLETE":
        findings.append(f"SPILL-VERDICT verdict={record.get('verdict')!r}; the census is either "
                        "complete or it is not reported as a census")
    return findings


def local_state(record: dict) -> str:
    """Machine state, reported and never compared: does this disk still look like the census?"""
    if not (REPO / ".hermes").is_dir():
        return "NOTHING_ON_THIS_MACHINE"
    totals: dict = {}
    for item in repo_legacy_census():
        totals[item["classification"]] = totals.get(item["classification"], 0) + item["bytes"]
    if totals == (record.get("repository_totals_bytes") or {}):
        return "MATCHES_RECORDED_TOTALS"
    return "DIFFERS_FROM_RECORDED_TOTALS"


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args(argv)
    objects = repo_legacy_census()
    homes = agent_home_discovery()
    totals = {}
    for item in objects:
        totals[item["classification"]] = totals.get(item["classification"], 0) + item["bytes"]
    document = {
        "schemaVersion": "design-lab/spill-census/v1",
        "task_key": TASK_KEY,
        "generated_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "subject_sha": git("rev-parse", "HEAD").strip(),
        "scope": {
            "inspected": ["DESIGN-LAB repository", "DESIGN-LAB .project-local", "agent homes at "
                          "path/metadata level"],
            "not_read": ["private chat content", "credentials", "unrelated agent sessions",
                         "sibling projects", "user personal asset libraries"],
            "never_touched": ["E:\\"],
            "shared_inputs": "declared in .project/paths.json (model-library, design-assets, "
                             "os-toolchain, design-toolchain) and NOT versioned by DESIGN-LAB, so "
                             "they are out of scope for this census",
        },
        "repository_legacy_objects": objects,
        "repository_totals_bytes": totals,
        "repository_total_mib": round(sum(totals.values()) / 1048576, 2),
        "agent_homes": homes,
        "design_lab_owned_in_agent_homes": {name: home["design_lab_owned"]
                                            for name, home in homes.items()
                                            if home["design_lab_owned"]},
        "verdict": "CENSUS_COMPLETE",
        "note": "Only the repository-side objects carry an owner of DESIGN-LAB. Nothing in an agent "
                "home is claimed by this project at this stage.",
    }
    if args.check:
        if not OUT.is_file():
            print("SPILL_CENSUS=FAIL missing " + OUT.name)
            return 1
        try:
            stored = json.loads(OUT.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError, ValueError) as exc:
            print(f"SPILL_CENSUS=FAIL unreadable {OUT.name} {type(exc).__name__}")
            return 1
        findings = record_findings(stored)
        for finding in findings:
            print("SPILL_CENSUS=FINDING " + finding)
        # The byte totals are a fact about this disk; saying it out loud is the point, deciding
        # the record's honesty from it never was.
        print(f"SPILL_CENSUS={'PASS' if not findings else 'FAIL'} "
              f"objects={len(stored.get('repository_legacy_objects') or [])} "
              f"rules={len(findings)} local_state={local_state(stored)}")
        return 0 if not findings else 1
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(document, indent=2, ensure_ascii=False) + "\n",
                   encoding="utf-8", newline="\n")
    print(f"SPILL_CENSUS=WRITTEN {OUT.relative_to(REPO)} objects={len(objects)} "
          f"total={document['repository_total_mib']} MiB")
    for item in objects:
        print(f"  {item['classification']:14} {item['bytes'] / 1048576:7.2f} MiB "
              f"{item['source_path']} -> {item['target_path'] or 'DO_NOT_TOUCH'} "
              f"[{item['delete_policy']}]")
    for name, home in homes.items():
        if home["exists"]:
            print(f"  agent home {name}: entries={home['native_entries_seen']} "
                  f"design-lab-owned={len(home['design_lab_owned'])} (content unread)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""DLDS-A030 / DLDS-A040 — classify the unverified DeepSeek delta.

The previous DeepSeek round committed 97 files against a taskpack that does not
exist on disk. This script freezes that delta and classifies every file:

* which real task it belongs to (an R5 product task or an authority-pack task),
* why it exists, who produces and consumes it, whether it duplicates something,
  whether it has a schema, tests and rollback,
* one of KEEP / KEEP_WITH_FIX / DUPLICATE / OUT_OF_PACK / UNPROVEN / REVERT.

Classification is data-driven from RULES below (an explicit, reviewable table),
never from memory. Anything not matched by a rule is reported as UNPROVEN, so a
file can never be silently accepted.

Writes:
    reports/current/DEEPSEEK-WORKTREE-INVENTORY.json
    reports/current/DEEPSEEK-WORKTREE-DIFF-SUMMARY.md

Usage:
    python scripts/deepseek_worktree_reconciliation.py            # write
    python scripts/deepseek_worktree_reconciliation.py --check    # verify drift
"""
from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
from datetime import datetime, timezone
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
INVENTORY = "reports/current/DEEPSEEK-WORKTREE-INVENTORY.json"
SUMMARY = "reports/current/DEEPSEEK-WORKTREE-DIFF-SUMMARY.md"
AUTHORITY_ID = "DL-TP-20260914-DEEPSEEK-AUTHORITY-R1"

# The delta produced by the unverified round: 4 commits on codex/r3-runtime-correctness.
# 9f34b53 is NOT part of it: that is the previous, legitimate R5 Photoshop/Comfy session
# commit, which was already local HEAD when the unverified round started.
DELTA_RANGE = "9f34b53..5631963"
DELTA_COMMITS = ["fdef778", "2a36f87", "4b10894", "5631963"]

# (path prefix, classification, attributed task(s), reason)
RULES = [
    ("src/design_lab/runtime/asset_store.py", "KEEP_WITH_FIX", ["DLDS-F020", "DL-R5-005"],
     "the v1 version insert now names its columns; required by any additive migration. "
     "DLDS-F020 re-audits it and its migration coverage."),
    ("src/design_lab/runtime/state_resources.py", "KEEP_WITH_FIX", ["DLDS-F020"],
     "registers one new immutable SQL resource; allow-list change only."),
    ("src/design_lab/creative/asset_versions.py", "KEEP_WITH_FIX", ["DL-R5-005", "DLDS-F030"],
     "version branch/parent/generation is the structural half of the R5-005 asset "
     "version manifest; needs the manifest half before R5-005 can claim anything."),
    ("src/design_lab/creative/version_guard.py", "KEEP_WITH_FIX", ["DL-R5-005", "DLDS-F040"],
     "rejected-version guard supports R5-005's 'no false success' and rollback acceptance."),
    ("src/design_lab/creative/lineage.py", "KEEP_WITH_FIX", ["DL-R5-022", "DLDS-F030"],
     "operation lineage is exactly R5-022's dependency graph (which downstream assets are "
     "affected by a change); no R5-022 acceptance run exists yet."),
    ("src/design_lab/creative/store.py", "KEEP_WITH_FIX", ["DLDS-F010", "DLDS-F020"],
     "additive migration runner; its migration is MIGRATION_CANDIDATE_PENDING_AUDIT until "
     "DLDS-F010 rehearses it on a database copy."),
    ("src/design_lab/creative/creative_job.py", "KEEP_WITH_FIX", ["DLDS-F030"],
     "CreativeJob is the identity layer DLDS-F030 requires (id/parent/state/evidence)."),
    ("src/design_lab/creative/requirement_ledger.py", "KEEP_WITH_FIX", ["DL-R5-014", "DLDS-F040"],
     "requirement acceptance needs artifact+readback; feeds the R5-014 preflight gate."),
    ("src/design_lab/creative/decision_ledger.py", "KEEP_WITH_FIX", ["DL-R5-014", "DLDS-F040"],
     "decision ledger with human-only gates matches R5-014's 'every accepted version has a "
     "human review receipt'."),
    ("src/design_lab/creative/session_link.py", "KEEP_WITH_FIX", ["DLDS-F030"],
     "correlation-only link to the requesting session; required boundary discipline."),
    ("src/design_lab/creative/generative/workflow_provider.py", "KEEP_WITH_FIX",
     ["DL-R5-008", "DLDS-F000"],
     "ComfyUI graph fingerprint/validation is R5-008's node-model fingerprint half; the live "
     "submit/cancel/reconnect half is Codex-side."),
    ("src/design_lab/creative/generative/partial_execution.py", "KEEP_WITH_FIX",
     ["DL-R5-022", "DL-R5-008"],
     "minimal sound re-run plan = R5-022 'unrelated assets are not regenerated'."),
    ("src/design_lab/creative/generative/remote_provider.py", "KEEP_WITH_FIX",
     ["DL-R5-006", "DLDS-G020"],
     "remote provider record structure; R5-006 requires cloud API to be separated from local "
     "models, which this does."),
    ("src/design_lab/creative/generative/model_assets.py", "KEEP_WITH_FIX", ["DL-R5-006"],
     "fail-closed model qualification/resolution; projects the DL-P1-100 radar rather than "
     "duplicating a registry."),
    ("src/design_lab/creative/media/audio_provider.py", "KEEP_WITH_FIX", ["DL-R5-016", "DL-R5-017"],
     "structural provider contract for TTS/music; the real device run is Codex-side."),
    ("src/design_lab/creative/media/three_d.py", "KEEP_WITH_FIX", ["DL-R5-020", "DLDS-F060"],
     "real byte-level GLB validator; DLDS-F060 requires it to be JSON-safe and to cover the "
     "full accessor matrix, which it currently does not."),
    ("src/design_lab/creative/media/video_boundary.py", "KEEP_WITH_FIX", ["DL-R5-019", "DLDS-F080"],
     "ownership boundary between DESIGN-LAB and a video host; DLDS-F080 requires capability "
     "ids instead of free-text host classes."),
    ("src/design_lab/assurance/qa_plane.py", "KEEP_WITH_FIX", ["DLDS-F070", "DL-R5-014"],
     "three QA planes with evidence ceilings; DLDS-F070 fixes the exact outcome vocabulary."),
    ("src/design_lab/assurance/human_jury.py", "KEEP_WITH_FIX", ["DLDS-F070", "DL-R5-014"],
     "jury record bound to an artifact digest; vocabulary must become APPROVE/REJECT per "
     "DLDS-F070, and no agent may ever sign."),
    ("src/design_lab/assurance/knowledge_feedback.py", "OUT_OF_PACK", [],
     "no R5 task and no authority task requires a knowledge-candidate export; the handoff "
     "states knowledge migration stays deferred. Parked, not deleted."),
    ("src/design_lab/readiness/host_matrix.py", "KEEP_WITH_FIX", ["DLDS-K000", "DL-R5-021"],
     "claimed-vs-verified host matrix; supports the no-overclaim audit required by K000."),
    ("src/design_lab/readiness/model_radar.py", "KEEP_WITH_FIX", ["DLDS-G020", "DLDS-G030", "DL-R5-006"],
     "model registry with licence/territory fields; H3 stays BLOCKED_BY_LICENSE."),
    ("src/design_lab/readiness/vector_provider.py", "OUT_OF_PACK", [],
     "no R5 or authority task requires a vectorisation provider SPI. Parked, not deleted."),
    ("src/design_lab/readiness/reconstruction_bench.py", "OUT_OF_PACK", [],
     "no task requires a reconstruction scoring bench; the existing R5-009/R5-013 scope does "
     "not include it. Parked, not deleted."),
    ("src/design_lab/interop/dtcg.py", "KEEP_WITH_FIX", ["DLDS-F050"],
     "DTCG provider; DLDS-F050 forbids relaxing the canonical schema, so the legacy-type "
     "allowance must move to an adapter."),
    ("src/design_lab/interop/timeline.py", "KEEP_WITH_FIX", ["DLDS-F050", "DL-R5-019"],
     "OTIO contract; DLDS-F050 requires official in_offset/out_offset transition semantics "
     "instead of a locally invented overlap truth."),
    ("src/design_lab/interop/provenance.py", "KEEP_WITH_FIX", ["DLDS-F050", "DL-R5-005"],
     "C2PA 2.4 mapping; DLDS-F050 requires the c2pa.claim.v2 / c2pa.signature baseline."),
    ("src/design_lab/interop/delivery_receipt.py", "KEEP_WITH_FIX", ["DL-R5-005", "DLDS-F000"],
     "delivery receipt is the manifest half of R5-005's delivery list."),
    ("src/design_lab/interop/penpot.py", "KEEP_WITH_FIX", ["DLDS-F050", "DL-R5-021"],
     "Penpot v3 archive contract; DLDS-F050 requires validating references inside the archive, "
     "not merely that it is a ZIP."),
    ("assurance-knowledge-candidate-v2.schema.json", "OUT_OF_PACK", [],
     "schema of the parked knowledge-candidate module."),
    ("test_assurance_knowledge_feedback.py", "OUT_OF_PACK", [],
     "tests of the parked knowledge-candidate module."),
    ("readiness-vector-provider.schema.json", "OUT_OF_PACK", [],
     "schema of the parked vector provider module."),
    ("test_readiness_vector_provider.py", "OUT_OF_PACK", [],
     "tests of the parked vector provider and bench modules."),
    ("src/design_lab/creative/", "KEEP_WITH_FIX", ["DLDS-F030"],
     "creative execution core package; identity layer required by DLDS-F030."),
    ("src/design_lab/assurance/", "KEEP_WITH_FIX", ["DLDS-F070"],
     "assurance package; DLDS-F070 fixes the QA and jury outcome vocabulary."),
    ("src/design_lab/readiness/", "KEEP_WITH_FIX", ["DLDS-G010", "DLDS-G020"],
     "readiness registries feeding the adapter and rights registry audits."),
    ("src/design_lab/interop/", "KEEP_WITH_FIX", ["DLDS-F050"],
     "interop package; DLDS-F050 fixes the DTCG/OTIO/C2PA/Penpot baselines."),
    ("design-lab/schemas/state/design-lab-state-creative-v1.sql", "KEEP_WITH_FIX", ["DLDS-F010"],
     "creative-v1 migration DDL; stays MIGRATION_CANDIDATE_PENDING_AUDIT until F010 rehearses it."),
    ("design-lab/schemas/", "KEEP_WITH_FIX", ["DLDS-F000"],
     "contract schemas; DLDS-F000 must show producer/consumer/receipt for each."),
    ("design-lab/tests/test_creative_generative.py", "KEEP_WITH_FIX", ["DLDS-H010", "DL-R5-006"],
     "unit tests for the generative contracts."),
    ("design-lab/tests/test_media_three_d.py", "KEEP_WITH_FIX", ["DLDS-F060", "DL-R5-020"],
     "GLB validator tests; DLDS-F060 will extend them for the accessor matrix."),
    ("design-lab/tests/", "KEEP_WITH_FIX", ["DLDS-H010"],
     "unit tests; DLDS-H010 requires the full forward/reverse/randomized gate."),
    ("design-lab/readiness/", "KEEP_WITH_FIX", ["DLDS-G010", "DLDS-G020"],
     "host matrix and model radar data; both feed the registry SSOT audit."),
    ("integrations/hosts/minimax-design/", "KEEP_WITH_FIX", ["DL-R5-021", "DL-R5-006", "DLDS-G020"],
     "MiniMax Design host candidate registration (E0, not launched); R5-021 asks for exactly "
     "a per-host version/interface/licence/minimal-case record."),
    ("docs/history/archive-2026-10-19/handoffs/DEEPSEEK-RIGHTS-REFRESH-MINIMAX-H3-2026-09-13.md", "REMOVED-2026-10-19", ["DL-R5-018", "DLDS-G030"],
     "H3 licence evidence record; H3 remains BLOCKED_BY_LICENSE and no run was performed; removed "
     "from the tree on owner order 2026-10-19 (summarised in docs/history/archive-2026-10-19/AGGREGATED-RECORD-2026-10-19.md)."),
    ("docs/history/archive-2026-10-19/handoffs/DEEPSEEK-OPEN-DESIGN-E3-READINESS-2026-09-13.md", "REMOVED-2026-10-19", ["DL-R5-021"],
     "Open Design E3 readiness and its concrete blocker (no runtime in the recorded scope); removed "
     "from the tree on owner order 2026-10-19 (summarised in docs/history/archive-2026-10-19/AGGREGATED-RECORD-2026-10-19.md)."),
    ("docs/history/archive-2026-10-19/handoffs/DEEPSEEK-DEEP-ADAPTATION-EXECUTION-2026-09-13.md", "REMOVED-2026-10-19", ["DLDS-A030"],
     "record of the unverified-attribution round, kept as incident evidence; the document was removed "
     "from the tree on owner order 2026-10-19 (summarised in docs/history/archive-2026-10-19/AGGREGATED-RECORD-2026-10-19.md, restore handle docs/history/archive-2026-10-19/REMOVALS.json)."),
    ("docs/history/archive-2026-10-19/handoffs/SESSION-RESTART-2026-09-12.md", "REMOVED-2026-10-19", ["DLDS-A020"],
     "previous session handoff, retained byte-identical by DLDS-A020; removed from the tree on "
     "owner order 2026-10-19 (summarised in docs/history/archive-2026-10-19/AGGREGATED-RECORD-2026-10-19.md, restore handle docs/history/archive-2026-10-19/REMOVALS.json)."),
    ("reports/current/", "KEEP_WITH_FIX", ["DLDS-H030"],
     "generated projections; DLDS-H030 regenerates them bound to an exact subject."),
    ("design-lab/config/current-report-index.json", "KEEP_WITH_FIX", ["DLDS-H030"],
     "report index; regenerated by the same generator."),
]


def git(*args: str) -> str:
    result = subprocess.run(["git", "-C", str(REPO), *args], capture_output=True, text=True,
                            encoding="utf-8", errors="replace")
    return result.stdout


def delta_files() -> list:
    out = git("diff", "--name-status", DELTA_RANGE)
    files = []
    for line in out.splitlines():
        parts = line.split("\t")
        if len(parts) >= 2:
            files.append({"status": parts[0].strip(), "path": parts[-1].strip()})
    return files


def classify(path: str) -> tuple:
    """Longest-prefix rule wins so specific rules beat directory rules."""
    best = None
    for prefix, classification, tasks, reason in RULES:
        if path == prefix or path.endswith("/" + prefix) or prefix in path:
            if best is None or len(prefix) > len(best[0]):
                best = (prefix, classification, tasks, reason)
    if best is None:
        return "UNPROVEN", [], "no rule matched: attribution must be supplied before this file may stay"
    return best[1], best[2], best[3]


def producer_consumer(path: str, tasks: list) -> tuple:
    if path.startswith("src/design_lab/"):
        return (f"module {path.split('/')[-1]}", "runtime callers and its own tests")
    if path.startswith("design-lab/tests/"):
        return ("unittest suite", "CI / scripts/run_python_tests.py")
    if path.startswith("design-lab/schemas/"):
        return ("contract author", "modules that validate against it")
    if path.startswith("reports/current/"):
        return ("scripts/generate_current_reports.py", "reviewers and governance gates")
    if path.startswith("docs/"):
        return ("the executing agent", "owner, Codex, future agents")
    if path.startswith("integrations/"):
        return ("adapter declaration", "host onboarding and the adapter registry")
    if path.startswith("design-lab/readiness/"):
        return ("readiness registry author", "host/model selection and G010/G020 audits")
    return ("unattributed", "unattributed")


# Explicit module -> test mapping. Several modules are covered by a grouped test
# module, so filename-stem matching alone would under-report coverage.
MODULE_TESTS = {
    "src/design_lab/creative/store.py": ["test_creative_migration.py", "test_creative_job.py"],
    "src/design_lab/creative/creative_job.py": ["test_creative_job.py"],
    "src/design_lab/creative/lineage.py": ["test_creative_lineage.py"],
    "src/design_lab/creative/asset_versions.py": ["test_creative_version_guard.py", "test_creative_migration.py"],
    "src/design_lab/creative/version_guard.py": ["test_creative_version_guard.py"],
    "src/design_lab/creative/requirement_ledger.py": ["test_creative_ledgers.py"],
    "src/design_lab/creative/decision_ledger.py": ["test_creative_ledgers.py"],
    "src/design_lab/creative/session_link.py": ["test_creative_session_link.py"],
    "src/design_lab/creative/generative/model_assets.py": ["test_creative_generative.py"],
    "src/design_lab/creative/generative/partial_execution.py": ["test_creative_generative.py"],
    "src/design_lab/creative/generative/remote_provider.py": ["test_creative_generative.py"],
    "src/design_lab/creative/generative/workflow_provider.py": ["test_creative_generative.py"],
    "src/design_lab/creative/media/audio_provider.py": ["test_media_audio.py"],
    "src/design_lab/creative/media/three_d.py": ["test_media_three_d.py"],
    "src/design_lab/creative/media/video_boundary.py": ["test_media_video_boundary.py"],
    "src/design_lab/assurance/qa_plane.py": ["test_assurance_qa_plane.py"],
    "src/design_lab/assurance/human_jury.py": ["test_assurance_jury.py"],
    "src/design_lab/readiness/host_matrix.py": ["test_readiness_host_matrix.py"],
    "src/design_lab/readiness/model_radar.py": ["test_readiness_model_radar.py"],
    "src/design_lab/interop/dtcg.py": ["test_interop_dtcg.py"],
    "src/design_lab/interop/timeline.py": ["test_interop_timeline.py"],
    "src/design_lab/interop/provenance.py": ["test_interop_provenance.py"],
    "src/design_lab/interop/delivery_receipt.py": ["test_interop_provenance.py"],
    "src/design_lab/interop/penpot.py": ["test_interop_penpot.py"],
    "design-lab/schemas/state/design-lab-state-creative-v1.sql": ["test_creative_migration.py"],
}
PACKAGE_TESTS = {
    "src/design_lab/creative": ["test_creative_job.py", "test_creative_migration.py"],
    "src/design_lab/creative/generative": ["test_creative_generative.py"],
    "src/design_lab/creative/media": ["test_media_audio.py", "test_media_three_d.py",
                                      "test_media_video_boundary.py"],
    "src/design_lab/assurance": ["test_assurance_qa_plane.py"],
    "src/design_lab/readiness": ["test_readiness_host_matrix.py"],
    "src/design_lab/interop": ["test_interop_dtcg.py"],
}


def has_test_for(path: str) -> bool:
    """Is there a real unittest module that exercises this file?"""
    if path.startswith("design-lab/tests/"):
        return True
    tests = REPO / "design-lab/tests"
    if not tests.is_dir():
        return False
    for name in MODULE_TESTS.get(path, []):
        if (tests / name).is_file():
            return True
    if path.endswith("__init__.py"):
        package = path.rsplit("/", 1)[0]
        return any((tests / name).is_file() for name in PACKAGE_TESTS.get(package, []))
    stem = Path(path).stem
    return any(stem in candidate.name for candidate in tests.glob("test_*.py"))


def tests_for(path: str) -> list:
    if path.startswith("design-lab/tests/"):
        return [Path(path).name]
    names = list(MODULE_TESTS.get(path, []))
    if not names and path.endswith("__init__.py"):
        names = list(PACKAGE_TESTS.get(path.rsplit("/", 1)[0], []))
    if not names:
        stem = Path(path).stem
        names = [c.name for c in (REPO / "design-lab/tests").glob("test_*.py") if stem in c.name]
    return sorted(set(names))


def build() -> dict:
    entries = []
    for item in delta_files():
        path = item["path"]
        classification, tasks, reason = classify(path)
        file_path = REPO / path
        producer, consumer = producer_consumer(path, tasks)
        same_name = [p for p in (REPO / "src").rglob(Path(path).name)
                     if p.is_file() and "design_lab" in str(p) and str(p.relative_to(REPO)).replace("\\", "/") != path]
        entries.append({
            "path": path,
            "git_status": item["status"],
            "bytes": file_path.stat().st_size if file_path.is_file() else None,
            "sha256": ("sha256:" + hashlib.sha256(file_path.read_bytes()).hexdigest())
                      if file_path.is_file() else None,
            "classification": classification,
            "attributed_tasks": [f"{AUTHORITY_ID}::{t}" if t.startswith("DLDS-") else t for t in tasks],
            "why_it_exists": reason,
            "producer": producer,
            "consumer": consumer,
            "duplicate_of": [str(p.relative_to(REPO)).replace("\\", "/") for p in same_name][:3],
            "has_schema": path.endswith(".schema.json") or path.endswith(".sql"),
            "has_tests": has_test_for(path),
            "tests": tests_for(path),
            "has_rollback": "revertible" if classification.startswith("KEEP") else "quarantine/restore path recorded",
        })
    counts = {}
    for entry in entries:
        counts[entry["classification"]] = counts.get(entry["classification"], 0) + 1
    return {
        "schemaVersion": "design-lab/deepseek-worktree-inventory/v1",
        "task_keys": [f"{AUTHORITY_ID}::DLDS-A030", f"{AUTHORITY_ID}::DLDS-A040"],
        "generated_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "frozen_delta": {"range": DELTA_RANGE, "commits": DELTA_COMMITS,
                         "branch": "codex/r3-runtime-correctness",
                         "note": "the DSH worktree was committed by the previous round; this "
                                 "inventory freezes that delta and attributes it file by file"},
        "current_worktree_clean": git("status", "--porcelain=v1").strip() == "",
        "current_branch": git("rev-parse", "--abbrev-ref", "HEAD").strip(),
        "current_sha": git("rev-parse", "HEAD").strip(),
        "classification_counts": counts,
        "unproven_paths": [e["path"] for e in entries if e["classification"] == "UNPROVEN"],
        "out_of_pack_paths": [e["path"] for e in entries if e["classification"] == "OUT_OF_PACK"],
        "entries": entries,
    }


def markdown(document: dict) -> str:
    lines = ["# DEEPSEEK WORKTREE DIFF SUMMARY — frozen delta", "",
             f"- Task: `{AUTHORITY_ID}::DLDS-A030` (+ A040 attribution)",
             f"- Delta: `{DELTA_RANGE}` on `codex/r3-runtime-correctness`",
             f"- Generated: {document['generated_at']}",
             f"- Current branch `{document['current_branch']}` at `{document['current_sha'][:12]}`, "
             f"worktree clean: {document['current_worktree_clean']}", "",
             "## Classification counts", ""]
    for name, count in sorted(document["classification_counts"].items()):
        lines.append(f"- `{name}`: {count}")
    lines += ["", "## Why this delta is not 'done' work", "",
              "The previous DeepSeek round executed items labelled `DL-P0-*`/`DL-P1-*` against a",
              "taskpack that exists nowhere on this disk. The code is real and its tests pass, but",
              "the task attribution is unverified, so nothing here counts as a completed task. Every",
              "file is therefore re-attributed to a real R5 product task or to a task of",
              f"`{AUTHORITY_ID}`, or parked as out-of-pack.", "",
              "## Files by classification", ""]
    current = None
    for entry in sorted(document["entries"], key=lambda e: (e["classification"], e["path"])):
        if entry["classification"] != current:
            current = entry["classification"]
            lines += [f"### {current}", "",
                      "| file | tasks | why |", "|---|---|---|"]
        tasks = ", ".join(entry["attributed_tasks"]) or "—"
        lines.append(f"| `{entry['path']}` | {tasks} | {entry['why_it_exists'][:150]} |")
    lines += ["", "## Out-of-pack files (parked, not deleted)", ""]
    for path in document["out_of_pack_paths"]:
        lines.append(f"- `{path}`")
    if document["unproven_paths"]:
        lines += ["", "## Unproven files (must be attributed before they stay)", ""]
        for path in document["unproven_paths"]:
            lines.append(f"- `{path}`")
    lines += ["", "## Rollback", "",
              "Every file is on an unmerged branch; `git revert` of the four delta commits, or",
              "restoring the quarantined out-of-pack files from",
              "`.project-local/quarantine/deepseek-round1/`, returns the tree to its prior state.", ""]
    return "\n".join(lines)


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args(argv)
    document = build()
    inventory_path = REPO / INVENTORY
    summary_path = REPO / SUMMARY
    if args.check:
        if not inventory_path.is_file():
            print(f"WORKTREE_INVENTORY=FAIL missing {INVENTORY}")
            return 1
        current = json.loads(inventory_path.read_text(encoding="utf-8"))
        if current["classification_counts"] != document["classification_counts"]:
            print("WORKTREE_INVENTORY=DRIFT classification changed")
            return 1
        print("WORKTREE_INVENTORY=PASS")
        return 0
    inventory_path.parent.mkdir(parents=True, exist_ok=True)
    inventory_path.write_text(json.dumps(document, indent=2, ensure_ascii=False) + "\n",
                              encoding="utf-8", newline="\n")
    summary_path.write_text(markdown(document), encoding="utf-8", newline="\n")
    print(f"WORKTREE_INVENTORY=WRITTEN {INVENTORY} files={len(document['entries'])} "
          + " ".join(f"{k}={v}" for k, v in sorted(document["classification_counts"].items())))
    if document["unproven_paths"]:
        print(f"UNPROVEN={len(document['unproven_paths'])}")
    print(f"OUT_OF_PACK={len(document['out_of_pack_paths'])}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

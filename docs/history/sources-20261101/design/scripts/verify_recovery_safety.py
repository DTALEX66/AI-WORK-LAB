#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""DLDS-I000 / DLDS-I010 — destructive-operation and unknown-outcome safety gate.

I000: every destructive operation must have a plan, a candidate list, a backup or
digest, verification, a rollback and a receipt. This checks the recorded manifests
of the three destructive tools this taskpack ran, and checks that those tools
expose the plan and restore modes their manifests promise.

I010: an attempt whose outcome is unknown must be reconciled, never silently
re-run. This reads the live state machine rather than a document: the set of
successors of OUTCOME_UNKNOWN must not contain RUNNING, terminal states must have
no successors, and a reconciliation API must demand a proof.

Writes reports/current/RECOVERY-SAFETY.json.

The verdict answers from tracked state only. I000 was measured on 2026-10-09 to read its
three receipts from ``.project-local``, which is gitignored, so in a clean checkout of the
commit that recorded PASS all three came back missing and the gate reported DRIFT -- a
destructive-operation receipt that survives only on one machine is a weak guard. Measured the
same day: the repository already held all three, byte-identical (sha256 prefixes 8cdfcbfa42dc1623
/ 044f02b896883e27 / 5088e4766929b68f), inside the preserved evidence bundle at
``docs/audits/DESIGN-LAB-UIKIT-CONFORMANCE-2026-09-28/session`` -- the duplicate-content audit is what showed it, after I had copied them a
second time under ``reports/history/`` and removed those copies again. The defect was never that
the bytes were unversioned, only that the gate read the gitignored ones. What the live copies
still hold on this machine is reported, never compared, so a clean CI checkout gets the same
judgement as this workstation.

Usage:
    python scripts/verify_recovery_safety.py [--check]
"""
from __future__ import annotations

import argparse
import hashlib
import inspect
import json
import re
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "src"))
OUT = REPO / "reports/current/RECOVERY-SAFETY.json"
TASK_KEYS = ["DL-TP-20260914-DEEPSEEK-AUTHORITY-R1::DLDS-I000",
             "DL-TP-20260914-DEEPSEEK-AUTHORITY-R1::DLDS-I010"]
AUTHORITY_ID = TASK_KEYS[0].split("::")[0]
OPERATION_ID = re.compile(r"DLDS-[A-Z]\d{3}")
RECEIPT_ROOT = "docs/audits/DESIGN-LAB-UIKIT-CONFORMANCE-2026-09-28/session"
# archived receipt -> (the tool that wrote it, the machine-local copy it was taken from)
MANIFESTS = {
    f"{RECEIPT_ROOT}/quarantine/deepseek-round1/RUNTIME-CLEANUP-MANIFEST.json": (
        "scripts/deepseek_runtime_cleanup.py",
        ".project-local/quarantine/deepseek-round1/RUNTIME-CLEANUP-MANIFEST.json"),
    f"{RECEIPT_ROOT}/quarantine/deepseek-round1/DELETE-MANIFEST.json": (
        "scripts/deepseek_quarantine_out_of_pack.py",
        ".project-local/quarantine/deepseek-round1/DELETE-MANIFEST.json"),
    f"{RECEIPT_ROOT}/hermes-legacy/MIGRATION-MANIFEST.json": (
        "scripts/deepseek_hermes_migration.py",
        ".project-local/archive/hermes-legacy/MIGRATION-MANIFEST.json"),
}
# Dated correction, 2026-10-09. The first version of this fix archived the three receipts under
# reports/history/destructive-receipts-2026-09-13 on the reasoning that a receipt living in
# .project-local "survives only on the machine that produced it". Measured, that was only half true:
# all three were already tracked, byte-identical (sha256 prefixes 8cdfcbfa42dc1623 /
# 044f02b896883e27 / 5088e4766929b68f), inside the preserved evidence bundle above -- the duplicate
# audit's own group list is what showed it. What was actually wrong was that the gate read the
# gitignored copies while the repository already held the bytes. Those three new files were removed
# in the same round; the bundle keeps the single tracked copy, and it is a preserved subtree
# (session/hermes-legacy holds 404 versioned files and 00-INDEX.md cites it), so if that bundle is
# ever relocated the versioned-input test below is what fails first.
UNKNOWN_OUTCOME_TESTS = ("design-lab/tests/test_runtime_attempt_safety.py",
                         "design-lab/tests/test_boot_reconciliation.py",
                         "design-lab/tests/test_native_tasks.py")
# A receipt must name the operation it receipts, and only address repository paths.
RECEIPT_TASK_KEY_FIELDS = ("task_key", "task_keys")
RECEIPT_PATH_FIELDS = ("path", "source", "target", "quarantined_to", "restore", "deleted_to")


def git(*args: str) -> str:
    return subprocess.run(["git", "-C", str(REPO), *args], capture_output=True, text=True,
                          encoding="utf-8", errors="replace").stdout.strip()


def file_digest(path: Path) -> str:
    return "sha256:" + hashlib.sha256(path.read_bytes()).hexdigest()


def repo_relative(rel: str) -> bool:
    """True when the receipt addresses a repository path, not a drive or a home directory."""
    text = str(rel).replace("\\", "/")
    if not text or text.startswith("/"):
        return False
    if re.match(r"^[A-Za-z]:", text):
        return False
    return not Path(text).is_absolute()


def tool_operation_ids(tool_source: str) -> set:
    """The operation ids the producing tool itself declares.

    One tool stamps several ids (the hermes migration writes E020/E030/E040 into one
    manifest), so the join is a set test rather than a single-key equality.
    """
    return set(OPERATION_ID.findall(tool_source))



def audit_manifest(rel: str, tool: str, live_rel: str) -> dict:
    """Audit one archived receipt, and report (never judge) the live copy on this machine."""
    path = REPO / rel
    audit = {"receipt": rel, "tool": tool, "live_copy": live_rel, "exists": False,
             "elements": {}, "ok": False}
    if not path.is_file():
        return audit
    document = json.loads(path.read_text(encoding="utf-8"))
    records = document.get("records") or document.get("deleted") or document.get("files") or []
    text = json.dumps(document, ensure_ascii=False).lower()
    elements = {
        "plan": bool(document.get("policy") or document.get("action") or document.get("recipe")
                     or document.get("task_key") or document.get("task_keys")),
        "candidate_list": bool(records),
        "backup_or_digest": all(bool(r.get("sha256") or r.get("digest") or r.get("verified_digest")
                                     or r.get("bytes") is not None) for r in records) if records else False,
        "verification": ("recreation" in text or "restore" in text or "verified" in text
                         or "reconcil" in text),
        "rollback": bool(document.get("restore_command") or "restore" in text
                         or "recreat" in text),
        "receipt": bool(document.get("schemaVersion") and (document.get("migrated_at")
                                                           or document.get("deleted_at")
                                                           or document.get("created_at"))),
    }
    tool_source = (REPO / tool).read_text(encoding="utf-8") if (REPO / tool).is_file() else ""
    tool_modes = {"plan_mode": "--plan" in tool_source, "restore_mode": "--restore" in tool_source}

    # Binding checks: all machine-independent, all answerable from the archived bytes.
    # Measured 2026-10-09: a receipt does NOT carry this gate's own I000/I010 keys -- each
    # operation is stamped with the id of the tool that performed it (DLDS-D030, DLDS-A040,
    # DLDS-E020..E040). So the join is receipt id <-> id declared in that tool's source.
    declared = set()
    for field in RECEIPT_TASK_KEY_FIELDS:
        value = document.get(field)
        declared.update(value if isinstance(value, list) else ([value] if value else []))
    off_authority = sorted(key for key in declared if not key.startswith(AUTHORITY_ID + "::"))
    foreign_ids = sorted({operation for key in declared
                          for operation in OPERATION_ID.findall(key)
                          if operation not in tool_operation_ids(tool_source)})
    unversioned = sorted({str(r.get(field)) for r in records for field in RECEIPT_PATH_FIELDS
                          if field in r and not repo_relative(r.get(field) or "")})
    tracked = git("ls-files", "--", rel)
    binding = {
        "names_the_tools_operation": bool(declared) and not foreign_ids and not off_authority,
        "receipt_task_keys": sorted(declared),
        "keys_outside_the_authority_pack": off_authority,
        "ids_the_producing_tool_never_declares": foreign_ids,
        "paths_are_repo_relative": not unversioned,
        "non_repository_paths": unversioned[:10],
        "receipt_is_versioned": bool(tracked),
    }
    live = REPO / live_rel
    if not live.is_file():
        copy_state = "LIVE_COPY_ABSENT"          # a clean checkout: expected, not a defect
    elif file_digest(live) == file_digest(path):
        copy_state = "MATCHES_ARCHIVED_COPY"
    else:
        copy_state = "DIFFERS_FROM_ARCHIVED_COPY"

    audit.update({
        "exists": True, "entries": len(records), "elements": elements, "tool_modes": tool_modes,
        "binding": binding,
        "archived_digest": file_digest(path),
        # Reported, never compared by --check: whether this machine still holds the same bytes.
        "live_copy_state": copy_state,
        "ok": (all(elements.values()) and all(tool_modes.values())
               and all(value for key, value in binding.items() if isinstance(value, bool))),
    })
    return audit



PRODUCTION_ROOT = REPO / "src" / "design_lab"
JOB_STORE_MODULE = "src/design_lab/runtime/job_store.py"
NATIVE_TASKS_MODULE = "src/design_lab/native_tasks.py"
SERVICE_MODULE = "src/design_lab/service.py"
RECOVERY_ENTRY_POINTS = ("recover_orphaned_attempts", "recover_interrupted",
                         "reconcile_attempt", "reconcile_receipted", "decide_native_recovery")


def python_sources(root):
    if not root.is_dir():
        return
    for path in sorted(root.rglob("*.py")):
        if "__pycache__" in path.parts:
            continue
        yield path


def production_call_sites(name, root=PRODUCTION_ROOT):
    """POSIX paths under the production package that call `name(...)`.

    Scoped to src/design_lab on purpose. The previous version of this gate counted
    a test file as proof that production behaves, which is exactly how a function
    with no caller at all passed for months.
    """
    pattern = re.compile(rf"\b{re.escape(name)}\s*\(")
    hits = []
    for path in python_sources(root):
        if not pattern.search(path.read_text(encoding="utf-8", errors="ignore")):
            continue
        try:
            hits.append(path.relative_to(REPO).as_posix())
        except ValueError:
            hits.append(path.relative_to(root.parent).as_posix())
    return hits


def executes_under_attempt_lock():
    """True only while NativeTasks.execute itself takes the attempt's OS lock.

    That hold is what turns "no holder" into "the worker is gone". Without it the
    liveness probe below would be guessing, and guessing is what A3 forbids.
    """
    path = REPO / "src" / "design_lab" / "native_tasks.py"
    if not path.is_file():
        return False
    source = path.read_text(encoding="utf-8", errors="ignore")
    start = source.find("    def execute(self,")
    if start < 0:
        return False
    body = source[start + 1:]
    following = body.find("\n    def ")
    if following >= 0:
        body = body[:following]
    return "recovery_lock(" in body and "RecoveryBusy" in body


def _method_body(path, signature):
    """The source lines of one method, read the same way executes_under_attempt_lock does."""
    source = path.read_text(encoding="utf-8", errors="ignore") if path.is_file() else ""
    start = source.find(signature)
    if start < 0:
        return ""
    body = source[start + len(signature):]
    following = body.find("\n    def ")
    return body[:following] if following >= 0 else body


def native_recovery_decision_is_wired():
    """The verified recovery entries must be reachable, and reachable only on a signature.

    This gate exists because reconcilable code with no caller passed for months. A
    restart that can only relabel is half a recovery: the unresolved attempt still
    needs somebody to decide it, so the decision path is checked end to end --
    a production caller, an authorization it cannot bypass, a refusal while a run
    is live, and no route back to the host.
    """
    tasks = REPO / NATIVE_TASKS_MODULE
    router = _method_body(tasks, "    def decide_recovery(self,")
    readback = _method_body(tasks, "    def recovery_decisions(self,")
    derived = _method_body(tasks, "    def _decision(self,")
    callers = [p for p in production_call_sites("decide_native_recovery") if p != SERVICE_MODULE]
    boot = [p for p in production_call_sites("recovery_readback") if p != SERVICE_MODULE]
    return {
        "decision_entry_exists": bool(router),
        "decision_production_callers": callers,
        "start_up_readback_callers": boot,
        "decision_requires_authorization": "RECOVERY_DECISION_AUTHORIZATION_REQUIRED" in router,
        # The refusal lives on the whole reachable path: the derivation probes the
        # OS lease and the router both raises for it and takes that same lock
        # around host cleanup, so a live run cannot start underneath a decision.
        "decision_refuses_live_run": ("RECOVERY_DECISION_WORKER_ACTIVE" in router
                                      and "_worker_active" in derived
                                      and "recovery_lock(" in router),
        "decision_reaches_verified_entries": ("reconcile_receipted(" in router
                                             and "quiesce_photoshop" in router
                                             and "quiesce_illustrator" in router),
        "decision_never_dispatches": "_dispatch(" not in router + readback + derived,
        "readback_invents_no_verdict": "_failed(" not in readback + derived
                                      and "_finish(" not in readback + derived,
    }


def decision_tests():
    """Tests count when they drive the readback AND an authorized decide, not before."""
    hits = []
    for rel in UNKNOWN_OUTCOME_TESTS:
        path = REPO / rel
        if not path.is_file():
            continue
        text = path.read_text(encoding="utf-8", errors="ignore")
        if (re.search(r"\brecovery_readback\s*\(", text)
                and re.search(r"\bdecide_native_recovery\s*\(", text)):
            hits.append(rel)
    return hits


def test_exercises_recovery(rel):
    """A test counts when it calls a recovery entry point, not when it contains a word."""
    path = REPO / rel
    if not path.is_file():
        return False
    text = path.read_text(encoding="utf-8", errors="ignore")
    return any(re.search(rf"\b{re.escape(name)}\s*\(", text) for name in RECOVERY_ENTRY_POINTS)


def audit_unknown_outcome() -> dict:
    from design_lab.runtime import job_store
    allowed = job_store.ALLOWED
    terminal = set(job_store.TERMINAL)
    findings = []
    if "OUTCOME_UNKNOWN" not in allowed:
        findings.append("the state machine has no OUTCOME_UNKNOWN state")
    else:
        successors = set(allowed["OUTCOME_UNKNOWN"])
        if "RUNNING" in successors:
            findings.append("OUTCOME_UNKNOWN may return to RUNNING: a silent re-run is possible")
        if not successors <= {"RECONCILING", "CANCEL_REQUESTED"}:
            findings.append(f"unexpected successors of OUTCOME_UNKNOWN: {sorted(successors)}")
    for state in terminal:
        if allowed.get(state):
            findings.append(f"terminal state {state} has successors")
    signature = inspect.signature(job_store.reconcile_attempt)
    if "proof" not in signature.parameters:
        findings.append("reconcile_attempt does not require a proof")
    if not hasattr(job_store, "recover_orphaned_attempts"):
        findings.append("no liveness-gated restart recovery entry point exists")

    # This used to be `hasattr(job_store, "recover_interrupted")`, which is true
    # for as long as the function is *defined* -- including the whole period in
    # which nothing called it. Existence is not the claim; a caller is.
    gated = [p for p in production_call_sites("recover_orphaned_attempts")
             if p != "src/design_lab/runtime/job_store.py"]
    blind = [p for p in production_call_sites("recover_interrupted")
             if p != "src/design_lab/runtime/job_store.py"]
    if not gated:
        findings.append("recover_orphaned_attempts has no production caller: restart "
                        "reconciles nothing")
    if blind:
        findings.append(f"the blind RUNNING scan is called from production: {blind}")

    # Without this, "the lock is free" would not mean "the worker is gone", and
    # the liveness probe above would be guessing.
    if not executes_under_attempt_lock():
        findings.append("NativeTasks.execute does not hold the attempt's recovery lock, "
                        "so a free lock cannot prove the worker stopped")

    covered = [rel for rel in UNKNOWN_OUTCOME_TESTS
               if test_exercises_recovery(rel)]
    if not covered:
        findings.append("no test calls a recovery entry point (a file merely "
                        "mentioning the word 'unknown' does not count)")
    decision = native_recovery_decision_is_wired()
    if not decision["decision_entry_exists"]:
        findings.append("no recovery decision entry point exists: an unresolved native "
                        "attempt can be relabelled but never decided")
    if not decision["decision_production_callers"]:
        findings.append("the recovery decision is unreachable from production: "
                        f"{NATIVE_TASKS_MODULE} defines it, nothing calls it")
    if not decision["start_up_readback_callers"]:
        findings.append("no start-up path reads what needs a decision, so a crash leaves "
                        "the operator with nothing to act on")
    for claim, present in (
            ("demands an authorization it cannot bypass", decision["decision_requires_authorization"]),
            ("refuses an attempt whose run is live", decision["decision_refuses_live_run"]),
            ("reaches the verified reconcile/quiesce entries",
             decision["decision_reaches_verified_entries"]),
            ("never dispatches to a host", decision["decision_never_dispatches"]),
            ("names no verdict it did not verify", decision["readback_invents_no_verdict"])):
        if not present:
            findings.append(f"the recovery decision path does not {claim}")
    if not decision_tests():
        findings.append("no test drives the start-up recovery decision path "
                        "(readback plus an authorized decide)")
    return {"outcome_unknown_successors": sorted(allowed.get("OUTCOME_UNKNOWN", [])),
            "terminal_states": sorted(terminal),
            "reconcile_requires_proof": "proof" in signature.parameters,
            "recovery_is_called_in_production": bool(gated),
            "recovery_production_callers": gated,
            "blind_scan_production_callers": blind,
            "execution_holds_attempt_lock": executes_under_attempt_lock(),
            "native_recovery_decision": decision,
            "tests": covered, "findings": findings, "ok": not findings}


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args(argv)
    manifests = [audit_manifest(rel, tool, live) for rel, (tool, live) in MANIFESTS.items()]
    recovery = audit_unknown_outcome()
    failures = [m["receipt"] for m in manifests if not m["ok"]]
    document = {
        "schemaVersion": "design-lab/recovery-safety/v2",
        "task_keys": TASK_KEYS,
        "checked_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "subject_sha": git("rev-parse", "HEAD"),
        "verdict_rule": "answerable from tracked state: the archived receipts, the three tools "
                        "in the repository, and the runtime state machine in src/. The live "
                        "copies under .project-local are reported as machine state and are "
                        "never compared, so a clean checkout judges the same as this disk.",
        "I000_destructive_operations": {
            "doctrine": "plan -> candidate list -> backup/digest -> verification -> rollback -> receipt",
            "receipt_archive_root": RECEIPT_ROOT,
            "manifests": manifests, "failures": failures,
        },
        "I010_unknown_outcome": {
            "rule": "an attempt with an unknown outcome is reconciled, never re-run; a failed or "
                    "cancelled attempt is never reported as completed",
            **recovery,
        },
        "verdict": "PASS" if not failures and recovery["ok"] else "FAIL",
    }
    if args.check:
        if not OUT.is_file():
            print("RECOVERY_SAFETY=DRIFT missing RECOVERY-SAFETY.json")
            return 1
        stored = json.loads(OUT.read_text(encoding="utf-8"))
        volatile = {"checked_at", "subject_sha"}

        def strip_machine(node):
            if isinstance(node, dict):
                return {key: strip_machine(value) for key, value in node.items()
                        if key != "live_copy_state"}
            if isinstance(node, list):
                return [strip_machine(item) for item in node]
            return node

        stored_part = {k: strip_machine(v) for k, v in stored.items() if k not in volatile}
        fresh_part = {k: strip_machine(v) for k, v in document.items() if k not in volatile}
        if stored_part != fresh_part:
            drifted = sorted({k for k in set(stored_part) | set(fresh_part)
                              if stored_part.get(k) != fresh_part.get(k)})
            print(f"RECOVERY_SAFETY=DRIFT fields changed since generation {drifted}")
            return 1
        copies = {}
        for item in manifests:
            copies[item["live_copy_state"]] = copies.get(item["live_copy_state"], 0) + 1
        print("RECOVERY_SAFETY=PASS receipts audited from tracked state "
              + " ".join(f"{key}={value}" for key, value in sorted(copies.items())))
        return 0
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(document, indent=2, ensure_ascii=False) + "\n", encoding="utf-8", newline="\n")
    print(f"RECOVERY_SAFETY={document['verdict']} manifests={len(manifests)} "
          f"manifest_failures={len(failures)} unknown_outcome_findings={len(recovery['findings'])}")
    for item in manifests:
        missing = [name for name, present in item["elements"].items() if not present]
        modes = [name for name, present in item.get("tool_modes", {}).items() if not present]
        binding = [name for name, present in item.get("binding", {}).items()
                   if isinstance(present, bool) and not present]
        print(f"  {'ok  ' if item['ok'] else 'FAIL'} {Path(item['receipt']).name:32} "
              f"entries={item.get('entries')} missing={missing or 'none'} modes={modes or 'ok'} "
              f"binding={binding or 'ok'} live={item.get('live_copy_state')}")
    for finding in recovery["findings"]:
        print("  FINDING:", finding)
    return 0 if document["verdict"] == "PASS" else 1



if __name__ == "__main__":
    raise SystemExit(main())

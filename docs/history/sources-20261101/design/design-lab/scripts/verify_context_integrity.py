#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""DL-CLOUD-2026-09-25 Prompt F: context-integrity gate (anti-amnesia, fail-closed).

Closes the four CI-layer items of Prompt F without creating a second
authority (the capsule/receipt it validates are GENERATED CONTEXT, marked
non-authoritative, and live under the gitignored ``.project-local``):

1. capsule / receipt schema validation -- every capsule field is present
   (a value, or an explicit ``{"absent": reason}``; never a guess);
2. stale-pointer check -- a capsule that no longer matches live main is
   reported STALE, and the gate refuses to let a session silently continue
   on it (``capsule_is_stale`` is the single source of that decision);
3. current-TaskPack link validation -- the AGENTS.md single-current
   pointer must resolve to a file that exists;
4. current-looking historical docs detector -- a historical doc
   (``docs/taskpacks/*``, ``reports/history/**``) that carries current
   phrasing without a SUPERSEDED marker fails the gate, because it will
   read as the current entry to the next fresh agent.

Nothing here mutates state; the gate only reads the tracked tree and the
capsule/receipt modules.
"""
from __future__ import annotations

import json
import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent.parent

# Historical surfaces the current-looking detector scans.
HISTORICAL_GLOBS = ("docs/taskpacks/*.md", "docs/taskpacks/**/*.md",
                    "reports/history/**/*.md")

# Phrasing that reads "current" to a fresh agent (the F1 failure mode: a
# 09-06 doc still claiming the 09-06 TaskPack is current).
CURRENT_LOOKING = re.compile(
    r"(当前统一|当前任务包|唯一 current|current integrated TaskPack(?!.*SUPERSEDED))",
    re.IGNORECASE,
)
SUPERSEDED_MARKER = re.compile(r"SUPERSEDED", re.IGNORECASE)


def _tracked(pattern: str) -> list[str]:
    r = subprocess.run(["git", "ls-files", "-z", pattern], cwd=ROOT, capture_output=True,
                       text=True, encoding="utf-8", errors="replace", check=False)
    return [p for p in r.stdout.split("\x00") if p]


def check_capsule_module() -> list[str]:
    """Import the capsule module and prove a freshly built capsule is complete
    and self-consistent (hermetic: no remote, no token)."""
    import importlib.util
    spec = importlib.util.spec_from_file_location(
        "context_capsule_under_test", ROOT / "design-lab" / "scripts" / "context_capsule.py")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    try:
        spec.loader.exec_module(module)
    except BaseException as exc:
        return [f"CAPSULE-MODULE-UNIMPORTABLE {exc}"]
    finally:
        sys.modules.pop(spec.name, None)

    findings: list[str] = []
    capsule = module.build_capsule(ROOT)
    for field in module.CAPSULE_FIELDS:
        if field not in capsule:
            findings.append(f"CAPSULE-MISSING-FIELD {field}")
        elif not (isinstance(capsule[field], str) or isinstance(capsule[field], dict)):
            findings.append(f"CAPSULE-BAD-FIELD-TYPE {field}")
        elif isinstance(capsule[field], dict) and "absent" not in capsule[field]:
            findings.append(f"CAPSULE-ABSENT-WITHOUT-REASON {field}")
    if capsule.get("non_authoritative") is not True:
        findings.append("CAPSULE-NON-AUTHORITATIVE-MARKER-MISSING")
    # A capsule built from the current checkout must be FRESH (no self-drift).
    stale = module.capsule_is_stale(capsule, ROOT)
    if stale:
        findings.append(f"CAPSULE-SELF-DRIFT {json.dumps(stale, ensure_ascii=False)}")
    return findings


def check_taskpack_pointer() -> list[str]:
    """AGENTS.md's single-current pointer must resolve to an existing file."""
    findings: list[str] = []
    agents = (ROOT / "AGENTS.md")
    if not agents.exists():
        return ["TASKPACK-POINTER-NO-AGENTS-MD"]
    text = agents.read_text(encoding="utf-8", errors="replace")
    m = re.search(r"`?(docs/taskpacks/([A-Z0-9\-]+)\.md)`?", text)
    if not m:
        findings.append("TASKPACK-POINTER-UNRESOLVED (no docs/taskpacks/*.md reference in AGENTS.md)")
        return findings
    target = ROOT / m.group(1)
    if not target.exists():
        findings.append(f"TASKPACK-POINTER-BROKEN {m.group(1)} (referenced but absent)")
    return findings


def check_current_looking_docs() -> list[str]:
    """A historical doc with current phrasing must carry SUPERSEDED."""
    findings: list[str] = []
    seen: set[str] = set()
    for pattern in HISTORICAL_GLOBS:
        for rel in _tracked(pattern):
            if rel in seen:
                continue
            seen.add(rel)
            text = (ROOT / rel).read_text(encoding="utf-8", errors="replace")
            if CURRENT_LOOKING.search(text) and not SUPERSEDED_MARKER.search(text):
                findings.append(
                    f"CURRENT-LOOKING-HISTORICAL-DOC {rel} "
                    "(current phrasing without a SUPERSEDED marker; add the marker or move the doc to docs/current/)")
    return findings


def check_receipt_module() -> list[str]:
    """A built receipt must reference the capsule by hash, not claim authority."""
    import importlib.util
    spec = importlib.util.spec_from_file_location(
        "context_capsule_receipt_under_test", ROOT / "design-lab" / "scripts" / "context_capsule.py")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    try:
        spec.loader.exec_module(module)
    except BaseException as exc:
        return [f"RECEIPT-MODULE-UNIMPORTABLE {exc}"]
    finally:
        sys.modules.pop(spec.name, None)
    findings: list[str] = []
    capsule = module.build_capsule(ROOT)
    receipt = module.build_receipt(
        capsule=capsule, task_id="gate-self-check", files_changed=["a.py"],
        commands=[], tests=[], evidence_ids=[], host_receipts=[],
        blockers=[], rollback="none", next_atomic_task="none")
    if receipt.get("non_authoritative") is not True:
        findings.append("RECEIPT-NON-AUTHORITATIVE-MARKER-MISSING")
    if "input_capsule_sha256" not in receipt:
        findings.append("RECEIPT-NO-INPUT-CAPSULE-HASH (a handoff must reference, not re-claim, context)")
    return findings


def main() -> int:
    findings = []
    findings += check_capsule_module()
    findings += check_receipt_module()
    findings += check_taskpack_pointer()
    findings += check_current_looking_docs()
    for f in sorted(findings):
        print(f"  {f}")
    if findings:
        print(f"\nVERIFY_CONTEXT_INTEGRITY=FAIL findings={len(findings)}")
        return 1
    print("\nVERIFY_CONTEXT_INTEGRITY=PASS capsule/receipt schemas + TaskPack pointer + current-looking detector clean")
    return 0


if __name__ == "__main__":
    sys.exit(main())

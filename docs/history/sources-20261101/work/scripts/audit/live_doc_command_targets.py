"""Scan the LIVE instruction surfaces for commands that point at a path which no longer exists.

A sentence describing an old layout is history and stays. A line that reads like something to run is
an instruction, and an instruction whose target is absent fails for whoever follows it. This is the
U02 path-convergence question asked as a machine check instead of a recollection: ERR-115 recorded
that `scripts/workflow/…` had moved, round D fixed the scripts that called it, and the *documents*
were never re-asked — 79 dead command references across 19 re-pointable paths and 14 that need a
human reason were still sitting in `docs/current/` and the managed skill references.

Surfaces: README.md, AGENTS.md, docs/current/**, config/**, packages/client-neutral-core/skills/**,
bin/**, apps/observer/README.md + module-profile.json. JSON ledgers and registries are deliberately
NOT scanned line-by-line: their `command` fields are history by contract (ERR-130) and their
promise-bearing fields already have their own gates.

Usage:
    python scripts/audit/live_doc_command_targets.py            # report
    python scripts/audit/live_doc_command_targets.py --apply     # re-point MAP entries in place
    python scripts/audit/live_doc_command_targets.py --json PATH

Exit: 0 clean, 1 dead references remain (report mode), 2 the scan itself could not run.
"""
from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
from pathlib import Path, PurePosixPath

REPO = Path(__file__).resolve().parents[2]

LIVE = ("README.md", "AGENTS.md", "docs/current/", "config/",
        "packages/client-neutral-core/skills/", "bin/",
        "apps/observer/README.md", "apps/observer/module-profile.json")

# Longest-first with \b: `js|…|json` matches the `js` inside `module-profile.json`, the exact defect
# ERR-130 records.
EXTS = r"python|jsonl|ya?ml|toml|markdown|cmd|exe|json|lock|mjs|cjs|sh|ps1|bat|js|py"
CMD_SHAPE = re.compile(
    r"(?:(?:python[\w.]*|bash|sh|pwsh|node|py)\s+|[\"'`(])"
    r"((?:[A-Za-z0-9_.\-/]+/)*(?:scripts|bin|services|packages|apps|tests|config|integrations|"
    r"docs|10-workflow|30-observer)/[A-Za-z0-9_.\-/]*\.(?:" + EXTS + r")\b)")

# Re-pointed on evidence: exactly one tracked file shares the basename, and that file is under a
# canonical module root (`.project/governance/module-ownership.json`).
MAP = {
    "bin/hermes-project-data.py": "packages/client-neutral-core/bin/hermes-project-data.py",
    "bin/hermes-project-terminal-guard.py":
        "packages/client-neutral-core/bin/hermes-project-terminal-guard.py",
    "integrations/executors/dsh/dsh_adapter.py": "services/execution-federation/dsh_adapter.py",
    "scripts/security/check_skill_provenance.py":
        "packages/client-neutral-core/scripts/security/check_skill_provenance.py",
    "scripts/security/scan_agent_rules.py":
        "packages/client-neutral-core/scripts/security/scan_agent_rules.py",
    "scripts/workflow/capsule.py": "packages/client-neutral-core/scripts/capsule.py",
    "scripts/workflow/config_compiler.py": "services/policy/config_compiler.py",
    "scripts/workflow/github_review_accelerator.py":
        "packages/client-neutral-core/scripts/github_review_accelerator.py",
    "scripts/workflow/github_upload_accelerator.py":
        "packages/client-neutral-core/scripts/github_upload_accelerator.py",
    "scripts/workflow/hermes_workflow_doctor.py":
        "integrations/executors/hermes/hermes_workflow_doctor.py",
    "scripts/workflow/machine_identity.py": "services/authority/machine_identity.py",
    "scripts/workflow/mcp_candidate_audit.py":
        "packages/client-neutral-core/scripts/mcp_candidate_audit.py",
    "scripts/workflow/skill_lifecycle.py": "packages/client-neutral-core/scripts/skill_lifecycle.py",
    "scripts/workflow/switch_model.py": "integrations/executors/hermes/switch_model.py",
    "scripts/workflow/sync_hermes_workflow_assets.py":
        "integrations/executors/hermes/sync_hermes_workflow_assets.py",
    "scripts/workflow/token_monitor.py": "packages/client-neutral-core/scripts/token_monitor.py",
    "scripts/workflow/verify_portable_install.py":
        "packages/client-neutral-core/scripts/verify_portable_install.py",
    "tests/test_token_monitor.py": "tests/workflow-assistance/test_token_monitor.py",
    "tests/test_workflow_governance.py": "tests/workflow-assistance/test_workflow_governance.py",
    "tests/test_codex_enhancement_boundary.py":
        "tests/workflow-assistance/test_codex_enhancement_boundary.py",
    "scripts/workflow/build_context_pack.py":
        "packages/client-neutral-core/scripts/build_context_pack.py",
    # the managed launchers are listed in AGENTS.md by their short names; the tracked copies live in
    # the enhancement module's bin/, which is where a reader must be sent
    "bin/codex.cmd": "packages/client-neutral-core/bin/codex.cmd",
    "bin/hermes-npx.cmd": "packages/client-neutral-core/bin/hermes-npx.cmd",
}

# Kept, on a stated reason, instead of edited blind. A gate that only ever sees the mechanical cases
# would quietly accept a doc instructing an invented path.
ALLOW = {
    "apps/observer/tests/test_observer_dashboard.py":
        "apps/observer/README.md names a test file that was never landed; the observer's real suites "
        "are apps/observer/tests/*.js and tests/workflow-assistance/. Not renamed here because "
        "guessing which suite the sentence meant would be invention — owner call.",
    "docs/current/workflow-assistance/workflow/examples/governance.yml":
        "Two docs point at an example file that does not exist. Authoring it would be inventing "
        "governance content; either the pointer is dropped or the example is written by an owner "
        "decision.",
    "docs/workflow/examples/governance.yml":
        "Pre-convergence spelling of the same missing example (wlg130-delivery-verdict.md).",
    "tests/test_release_manifest.py":
        "Illustrative filename in a python-testing reference, not this repository's path.",
    # The 2026-10-09 cutover record (docs/history/archive/ui-priority-20261009/LEGACY-TASK-DISPOSITION.json) is a
    # per-row account of what happened to the OLD ledger's claims. Its quoted paths are the historical
    # object of the sentence, not instructions, so re-pointing one to a file that happens to exist today
    # would rewrite the record. Each entry below is measured with `git log --all -1 --format=%h -- <path>`
    # on 2026-10-10: "in history" means it existed at some point in this repository, "never" means it did
    # not, and a name that never existed here belongs to the foreign tree the quoted row was about.
    "10-workflow/workflow-assistance/config/codex-enhancement-boundary.json":
        "IN HISTORY, removed at the 2026-09 directory convergence (AGENTS.md: the legacy "
        "10-workflow/workflow-assistance path was split out and is no longer tracked). Named by a "
        "disposition row that exists precisely to record that removal.",
    "HERMES_HOME/bin/hermes.exe":
        "A Hermes Home launcher path, outside the repository by design (AGENTS.md: `bin/` is a Hermes-Home "
        "overlay path whose tracked sources live under packages/client-neutral-core/bin/). A repo-relative "
        "existence check cannot and must not resolve it.",
    "apps/observer/tests/helpers.js":
        "IN HISTORY, since deleted. Quoted by a disposition row about an old test-side file, not offered as "
        "something to run.",
    "scripts/run-tests.cjs":
        "IN HISTORY, since deleted at the frontend convergence. Same: a quoted historical operand.",
    "tests/test_render_v3.js":
        "NEVER in this repository's history. The disposition row inherits a claim written against the frozen "
        "source document's own tree, so the name is evidence about that record, not a path here.",
    "tests/test_observer_canonical.py":
        "NEVER in this repository's history; same foreign-tree spelling as tests/test_render_v3.js above.",
    "tests/test_observer_dashboard_render.py":
        "NEVER in this repository's history; same foreign-tree spelling.",
    "scripts/verify_open_design_assistance.py":
        "NEVER in this repository's history. The Open Design assistance migration belongs to "
        "DTALEX66/DESIGN-LAB's domain (AGENTS.md: two distinct identities), so the row quotes the other "
        "project's verifier name.",
    "tests/run_all_tests.js":
        "NEVER at this spelling in this repository (the tracked runner is apps/observer/tests/run_all_tests.js). "
        "Deliberately NOT re-pointed: the string sits inside LEGACY-TASK-DISPOSITION.json, whose quoted paths "
        "are the historical object of each row, and rewriting them would falsify the record.",
    "tests/test_evidence_connectors.py":
        "Illustrative filename in a python-testing reference, not this repository's path.",
    "scripts/run_bakeoff.py":
        "Illustrative script name inside a generic testing lesson.",
    "scripts/check_repository_conventions.py":
        "Illustrative example in a generic testing lesson; no such tool is owned here.",
    "vite/bin/vite.js":
        "Generic Vite invocation inside a skill reference about third-party bundling.",
    "apps/x/node_modules/vite/bin/vite.js":
        "Anatomy of a foreign project's bundle path, drawn to explain a failure mode.",
    "scripts/test.py":
        "Illustrative guard-hook test filename in a reference document.",
    "bin/cli.js":
        "Illustrative example inside a writeback reference about another tool's layout.",
    "scripts/ci/run_tests.sh":
        "Hypothetical wrapper filename inside a lesson about two git-bash traps (`pwd` MSYS paths "
        "and a leading `--`). No such file is owned here — the only tracked .sh is "
        "scripts/setup-workflow.sh and the sanctioned runner is "
        "scripts/ci/run_root_governance_suite.py.",
    "scripts/run_tests.sh":
        "The same lesson's second mention of that hypothetical wrapper, used to explain why "
        "`bash x.sh -- -x` breaks. Not a repository path.",
    "apps/desktop/release/win-unpacked/Hermes.exe":
        "AGENTS.md writes Hermes' official install layout relative to Hermes Home, not to this "
        "repository; the root is resolved from the uninstall registry entry or the shortcut "
        "TargetPath (five-dimension baseline, ERR-088), so no repo file is meant.",
    "scripts/workflow/sync_codex_global_assets.py":
        "No tracked successor carries this name; Codex global-asset deployment now runs through "
        "packages/client-neutral-core/scripts/deploy_global_rules.py. All five citations sit in "
        "dated 2026-08 investigation documents (codex-desktop-update-state-investigation-2026-08-13.md), "
        "so they are historical narrative that happens to live under docs/current/ — a layout "
        "finding for U02, not a command to re-issue blind.",
    "scripts/workflow/execution_preflight.py":
        "Only tests/workflow-assistance/test_execution_preflight.py survives under this name; no "
        "module of that name is tracked. Cited from the dated codex-execution-reliability note.",
    "scripts/workflow/user_profile_export.py":
        "Only tests/workflow-assistance/test_user_profile_export.py survives; the export module is "
        "not tracked under this name. Cited from user-environment-profile.md and "
        "codex-global-enhancement.md.",
    "tests/workflow-assistance/test_x.py":
        "Placeholder filename inside a generic python-testing lesson, not a real module.",
    "/usr/bin/link.exe":
        "Names the MSYS `link` binary that shadows MSVC's link.exe — an external path described in "
        "a lesson, never a repository target.",
    "scripts/Enter-ArcheAxisDev.ps1":
        "Older dev-environment wrapper convention, mentioned in a lesson about Windows quoting and "
        "path traps. Neither .ps1 is tracked.",
    "scripts/Exit-ArcheAxisDev.ps1":
        "The matching half of that retired convention, cited in the same lesson.",
}


def tracked_files() -> list[str]:
    raw = subprocess.run(["git", "-c", "core.quotePath=false", "ls-files", "-z"],
                         cwd=REPO, capture_output=True).stdout.split(b"\0")
    return [p.decode("utf-8", "replace") for p in raw if p]


def scan(files: list[str]) -> list[dict]:
    hits = []
    for rel in files:
        if not rel.startswith(LIVE):
            continue
        p = REPO / rel
        if not p.is_file():
            continue
        text = p.read_text(encoding="utf-8", errors="replace")
        for n, line in enumerate(text.splitlines(), 1):
            for m in CMD_SHAPE.finditer(line):
                ref = re.sub(r"^\./", "", m.group(1))
                if (REPO / PurePosixPath(ref)).exists():
                    continue
                leaf = PurePosixPath(ref).name
                if any(c in leaf for c in "{*}") or "XX" in leaf.upper():
                    continue
                hits.append({"file": rel, "line": n, "reference": ref, "text": line.strip()[:170]})
    return hits


def unresolved(hits: list[dict]) -> list[dict]:
    """Hits that are neither re-pointable nor allowed — the state the gate refuses."""
    out = []
    for h in hits:
        if h["reference"] in MAP:
            continue
        if h["reference"] in ALLOW:
            continue
        out.append(h)
    return out


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--apply", action="store_true", help="rewrite MAP targets inside live files")
    ap.add_argument("--json", default=None)
    args = ap.parse_args()

    files = tracked_files()
    overlap = sorted(set(MAP) & set(ALLOW))
    if overlap:
        print("MAP_AND_ALLOW_OVERLAP " + ", ".join(overlap) +
              " — a path cannot be both re-pointed and kept")
        return 2

    missing_targets = {k: v for k, v in MAP.items() if not (REPO / v).is_file()}
    if missing_targets:
        print("MAP_TARGET_ABSENT " + json.dumps(missing_targets, ensure_ascii=False))
        return 2

    if args.apply:
        changed = {}
        for rel in files:
            if not rel.startswith(LIVE):
                continue
            p = REPO / rel
            text = p.read_text(encoding="utf-8", errors="replace")
            new = text
            for dead, live in MAP.items():
                # anchored, not a bare str.replace: a doc that already says
                # packages/client-neutral-core/bin/codex.cmd CONTAINS the dead key `bin/codex.cmd`,
                # and an unanchored replace turns a correct path into
                # packages/client-neutral-core/packages/client-neutral-core/… (this happened)
                pattern = re.compile(r"(?<![\w./-])" + re.escape(dead))
                new, n = pattern.subn(live, new)
                if n:
                    changed.setdefault(dead, []).append(rel)
            if new != text:
                p.write_text(new, encoding="utf-8", newline="")
                back = p.read_text(encoding="utf-8", errors="replace")
                for dead in MAP:
                    # the rewritten text legitimately CONTAINS e.g. `bin/codex.cmd` inside
                    # `packages/client-neutral-core/bin/codex.cmd`, so assert no *unprefixed*
                    # occurrence is left rather than plain substring absence
                    leftover = re.search(r"(?<![\w./-])" + re.escape(dead), back)
                    assert leftover is None, (rel, dead, back[max(0, leftover.start() - 60):
                                                             leftover.start() + 90])
        print(f"files_rewritten={len(set(sum(changed.values(), [])))} "
              f"paths_repointed={len(changed)}")
        for dead, where in sorted(changed.items()):
            print(f"  {dead} -> {MAP[dead]}  ({len(set(where))} file(s))")

    hits = scan(files)
    rest = unresolved(hits)
    repointed = [h for h in hits if h["reference"] in MAP]
    allowed = [h for h in hits if h["reference"] in ALLOW]
    doc = {"schemaVersion": "work-lab/live-doc-command-targets/v1",
           "liveSurfaces": list(LIVE),
           "counts": {"deadReferencesTotal": len(hits), "repointedByMap": len(repointed),
                      "allowedWithReason": len(allowed), "unresolved": len(rest),
                      "distinctAllowedPaths": len({h['reference'] for h in allowed})},
           "map": MAP, "allow": ALLOW,
           "unresolvedRows": rest,
           "repointRows": [{"file": h["file"], "line": h["line"], "reference": h["reference"]}
                           for h in repointed],
           }
    if args.json:
        out = Path(args.json)
        out = out if out.is_absolute() else REPO / out
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(json.dumps(doc, ensure_ascii=False, indent=2), encoding="utf-8")
        print(f"report -> {out.relative_to(REPO).as_posix()}")
    print(f"RESULT dead={len(hits)} repointed={len(repointed)} allowed={len(allowed)} "
          f"unresolved={len(rest)}")
    for h in rest:
        print(f"  UNRESOLVED {h['file']}:{h['line']} -> {h['reference']}")
    return 1 if rest else 0


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    raise SystemExit(main())

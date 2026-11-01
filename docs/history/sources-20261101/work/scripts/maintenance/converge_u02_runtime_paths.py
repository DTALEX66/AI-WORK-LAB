"""U02: converge the remaining stale runtime paths and two dead links onto current roots.

Each replacement is asserted (exactly one hit, and the new text present after the write),
so a silent miss cannot be reported as a fix.
"""
import pathlib
import re
import sys

EDITS = [
    # The sync entry point moved to the adapter surface; both bootstrap scripts still
    # pointed at scripts/workflow/, which does not exist — a --apply run could not start.
    ("scripts/setup-workflow.sh",
     '"$PY_REPO_ROOT/scripts/workflow/sync_hermes_workflow_assets.py"',
     '"$PY_REPO_ROOT/integrations/executors/hermes/sync_hermes_workflow_assets.py"'),
    ("scripts/setup-workflow.sh",
     'PLAN_FILE="$REPO_ROOT/.hermes/task-artifacts/setup-plan.json"',
     'PLAN_FILE="$REPO_ROOT/.project-local/artifacts/setup-plan.json"'),
    ("scripts/setup-workflow.ps1",
     '$SyncScript = Join-Path $RepoRoot "scripts\\workflow\\sync_hermes_workflow_assets.py"',
     '$SyncScript = Join-Path $RepoRoot "integrations\\executors\\hermes\\sync_hermes_workflow_assets.py"'),
    ("scripts/setup-workflow.ps1",
     '$PlanFile = Join-Path $RepoRoot ".hermes\\task-artifacts\\setup-plan.json"',
     '$PlanFile = Join-Path $RepoRoot ".project-local\\artifacts\\setup-plan.json"'),
    # A per-project cache belongs in the project-local run root, not in the Hermes home.
    ("packages/client-neutral-core/scripts/skill_call_index.py",
     'INDEX_FILE = ".hermes/skill-call-index.json"',
     'INDEX_FILE = ".project-local/runs/skill-call-index.json"'),
    ("docs/decisions/global-execution-standard.md",
     "先查项目技能调用索引（.hermes/skill-call-index.json）",
     "先查项目技能调用索引（.project-local/runs/skill-call-index.json）"),
    ("docs/decisions/global-execution-standard.md",
     "索引：.hermes/skill-call-index.json",
     "索引：.project-local/runs/skill-call-index.json"),
    # generate_current_state.py writes .project-local/artifacts/current-state-ci.json,
    # while this verifier looked for it under .hermes/task-artifacts/ — so on a machine
    # where the evidence exists it was still reported as absent.
    ("packages/client-neutral-core/scripts/verify_gate_runtime_convergence.py",
     'evidence_file = ROOT / ".hermes/task-artifacts/current-state-ci.json"',
     'evidence_file = ROOT / ".project-local/artifacts/current-state-ci.json"'),
    ("packages/client-neutral-core/scripts/verify_gate_runtime_convergence.py",
     "On CI runners the local CI-evidence file (.hermes/task-artifacts/\n    current-state-ci.json)",
     "On CI runners the local CI-evidence file\n    (.project-local/artifacts/current-state-ci.json)"),
]

WORKSPACE_NEW = """{
  "folders": [
    { "name": "WORK-LAB Root", "path": "." },
    { "name": "Client-neutral Core", "path": "packages/client-neutral-core" },
    { "name": "Observer (read-only projection)", "path": "apps/observer" },
    { "name": "Services (orchestration/policy/receipts)", "path": "services" },
    { "name": "Governance", "path": ".project/governance" }
  ],
  "settings": {
    "files.exclude": { ".project-local": true },
    "search.exclude": {
      ".project-local": true,
      "**/node_modules": true,
      "**/dist": true,
      "**/build": true
    }
  }
}
"""

problems = []
for rel, old, new in EDITS:
    p = pathlib.Path(rel)
    text = p.read_text(encoding="utf-8")
    hits = text.count(old)
    if hits != 1:
        problems.append(f"{rel}: needle hits={hits} for {old[:52]!r}")
        continue
    p.write_text(text.replace(old, new, 1), encoding="utf-8", newline="")
    back = p.read_text(encoding="utf-8")
    if new not in back or old in back:
        problems.append(f"{rel}: write did not land")

ws = pathlib.Path("WORK-LAB.code-workspace")
old_ws = ws.read_text(encoding="utf-8")
ws.write_text(WORKSPACE_NEW, encoding="utf-8", newline="\n")
print("workspace replaced:", ws.read_text(encoding="utf-8") == WORKSPACE_NEW)
dead = [w for w in re.findall(r'"path":\s*"([^"]+)"', WORKSPACE_NEW)
        if w != "." and not pathlib.Path(w).exists()]
print("workspace_dead_folder_entries:", dead or "NONE")

# Nothing in the tracked tree should still route runtime output into Hermes home.
leftover = []
for path in pathlib.Path(".").rglob("*"):
    if not path.is_file() or path.parts[0] in {".git", ".project-local"}:
        continue
    if path.suffix not in {".py", ".sh", ".ps1", ".md", ".json", ".yaml", ".yml"}:
        continue
    try:
        body = path.read_text(encoding="utf-8", errors="replace")
    except OSError:
        continue
    if ".hermes/task-artifacts/setup-plan" in body or ".hermes/skill-call-index" in body \
       or "scripts/workflow/sync_hermes_workflow_assets.py" in body \
       or 'ROOT / ".hermes/task-artifacts/current-state-ci.json"' in body:
        leftover.append(path.as_posix())
print("stale_routing_paths_remaining:", leftover or "NONE")

if problems:
    print("PROBLEMS:")
    for x in problems:
        print("  ", x)
    sys.exit(1)
print("U02_EDITS_APPLIED", len(EDITS))

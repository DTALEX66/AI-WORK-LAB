"""P0-02 real-path verification: which paths project-definition.md references
actually exist on main. Output a verdict dict for the doc repair."""
import subprocess, os, json
from pathlib import Path

ROOT = Path(os.environ.get("WORKLAB_ROOT", r"D:\All projects\WORK-LAB"))

def tracked(patterns):
    out = subprocess.run(["git", "ls-files"], cwd=ROOT, capture_output=True, text=True, encoding="utf-8", errors="replace").stdout
    lines = [l for l in out.splitlines() if l.strip()]
    res = {}
    for name, pat in patterns.items():
        res[name] = [l for l in lines if pat.match(l)]
    return res

import re
P = lambda s: re.compile(s)
res = tracked({
    "client_neutral_manifest": P(r"^packages/client-neutral-core/workflow-manifest\.yaml$"),
    "client_neutral_scripts": P(r"^packages/client-neutral-core/scripts/"),
    "client_neutral_bin": P(r"^packages/client-neutral-core/bin/"),
    "client_neutral_skills": P(r"^packages/client-neutral-core/skills/"),
    "setup_workflow_sh": P(r"^scripts/setup-workflow\.sh$"),
    "setup_workflow_ps1": P(r"^scripts/setup-workflow\.ps1$"),
    "setup_sh_root": P(r"^setup\.sh$"),
    "setup_ps1_root": P(r"^setup\.ps1$"),
    "bin_root": P(r"^bin/"),
    "skills_root": P(r"^skills/"),
    "scripts_workflow": P(r"^scripts/workflow/"),
    "scripts_security_scan": P(r"^scripts/security/scan_agent_rules\.py$"),
    "docs_workflow": P(r"^docs/workflow/"),
    "config_yaml": P(r"^config/config\.yaml$"),
    "config_env_template": P(r"^config/\.env\.template$"),
    "sync_hermes": P(r"sync_hermes_workflow_assets\.py$"),
    "doctor": P(r"hermes_workflow_doctor\.py$"),
    "switch_model": P(r"switch_model\.py$"),
    "ci_watcher": P(r"ci_watcher\.py$"),
    "growth_candidates": P(r"growth_candidates\.py$"),
    "growth_watcher": P(r"growth_watcher\.py$"),
    "impact_planner": P(r"impact_planner\.py$"),
    "run_taskpack_agent": P(r"run_taskpack_agent\.py$"),
    "task_ledger": P(r"task_ledger\.py$"),
    "model_policy": P(r"^services/policy/model_policy\.py$"),
})

# also: does docs/current/workflow-assistance/workflow/ dir track other files
dc = [l for l in subprocess.run(["git","ls-files","docs/current/"], cwd=ROOT, capture_output=True, text=True, encoding="utf-8", errors="replace").stdout.splitlines() if l.strip()]
res["docs_current_all"] = dc

print(json.dumps(res, indent=2, ensure_ascii=False))

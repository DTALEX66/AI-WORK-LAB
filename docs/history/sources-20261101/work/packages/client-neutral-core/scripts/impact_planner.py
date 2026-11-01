#!/usr/bin/env python3
"""Build a deterministic, read-only Gate Plan from changed paths and a project profile."""

from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
from fnmatch import fnmatch
from pathlib import Path
from typing import Any

import yaml
from jsonschema import Draft202012Validator, FormatChecker

SCHEMA = Path(__file__).resolve().parents[2] / "contracts" / "schemas" / "workflow" / "gate-plan.schema.json"


def _git(root: Path, *args: str) -> str:
    result = subprocess.run(["git", *args], cwd=root, text=True, encoding="utf-8", errors="replace", capture_output=True, check=False)
    if result.returncode:
        raise RuntimeError(f"git {' '.join(args)} failed: {result.stderr.strip()}")
    return result.stdout.strip()


def _matches(path: str, patterns: list[str]) -> bool:
    normalized = path.replace("\\", "/")
    return any(fnmatch(normalized, pattern) or normalized.startswith(pattern.rstrip("*") .rstrip("/")) for pattern in patterns)


def _digest(payload: dict[str, Any]) -> dict[str, str]:
    digest_payload = {
        key: value for key, value in payload.items() if key not in {"generated_at", "plan_id"}
    }
    canonical = json.dumps(digest_payload, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return {"algorithm": "sha256", "value": hashlib.sha256(canonical).hexdigest()}


def load_profile(path: Path) -> dict[str, Any]:
    profile = yaml.safe_load(path.read_text(encoding="utf-8"))
    declared_schema = profile.get("schema_version", profile.get("schema")) if isinstance(profile, dict) else None
    if declared_schema != "workflow/project-profile/v1" and declared_schema != "work-lab-project-profile/v1":
        raise ValueError("profile must declare schema workflow/project-profile/v1")
    for key in ("project", "modules", "risk_zones", "gates", "ci"):
        if not isinstance(profile.get(key), dict):
            raise ValueError(f"profile field must be an object: {key}")
    # A module root without a gate of the same id is a mapping that can never select work: a change
    # inside it would be "known" to the planner and still require nothing. Refuse the profile instead
    # of shipping a fail-open classifier (proven on 2026-10-08: required_gates=[] , risk=medium).
    ungated = sorted(set(profile["modules"]) - set(profile["gates"]))
    if ungated:
        raise ValueError(
            f"profile declares modules with no same-named gate: {ungated}; "
            "every module root must map to a gate that can be required"
        )
    return profile


def build_plan(
    profile: dict[str, Any],
    *,
    repository: str,
    commit: str,
    tree: str,
    changed_paths: list[str],
    delivery_effect: str = "none",
    platform_scope: list[str] | None = None,
    plan_id: str = "plan-local",
    generated_at: str = "2026-08-07T00:00:00Z",
) -> dict[str, Any]:
    modules = profile["modules"]
    gates = profile["gates"]
    direct: set[str] = set()
    critical = False
    unknown_paths: list[str] = []
    for path in changed_paths:
        normalized_path = path.replace("\\", "/")
        path_selected: set[str] = set()
        if _matches(normalized_path, profile.get("risk_zones", {}).get("critical", [])):
            critical = True
        for gate_id, gate in gates.items():
            gate_paths = gate.get("paths", []) if isinstance(gate, dict) else []
            if _matches(normalized_path, gate_paths):
                direct.add(gate_id)
                path_selected.add(gate_id)
        matched = False
        for module_id, module in modules.items():
            roots = module.get("roots", []) if isinstance(module, dict) else []
            if any(normalized_path.startswith(root.rstrip("/") + "/") or normalized_path == root for root in roots):
                matched = True
                if module_id in gates:
                    direct.add(module_id)
                    path_selected.add(module_id)
        # "Unknown" means the change is not classified by EITHER mechanism. Judging it only by module
        # roots made a path that a gate explicitly lists look unclassified, which escalated it to every
        # gate and, worse, described a mapped surface as unmapped.
        if not matched and not path_selected:
            unknown_paths.append(normalized_path)

    reverse: dict[str, set[str]] = {name: set() for name in modules}
    for module_id, module in modules.items():
        for dependency in module.get("depends_on", []) if isinstance(module, dict) else []:
            reverse.setdefault(dependency, set()).add(module_id)
    affected = set(direct)
    queue = list(direct)
    while queue:
        current = queue.pop(0)
        for dependent in sorted(reverse.get(current, set())):
            if dependent not in affected:
                affected.add(dependent)
                queue.append(dependent)

    # critical prefixes (.project/governance/**, .github/**, scripts/ci/**) are
    # already covered by risk_zones.critical above; only unknown paths add a
    # fail-closed critical here.
    if unknown_paths:
        critical = True
    if changed_paths and not direct:
        # Something changed and the mapping selected no gate at all. Whether the path matched no root
        # or matched a root whose gate is missing, the answer is the same: this work is not covered, so
        # escalate to every gate instead of returning an empty plan that reads like a cheap PASS.
        critical = True
    if critical:
        affected.update(gates)

    required = sorted(affected)
    skipped = [
        {"gate_id": gate_id, "reason": "no changed path or transitive dependency selected this gate"}
        for gate_id in sorted(gates)
        if gate_id not in affected
    ]
    payload: dict[str, Any] = {
        "schema_version": "workflow/gate-plan/v1",
        "plan_id": plan_id,
        "source_identity": {
            "repository": repository,
            "commit": {"algorithm": "repository-default", "object_type": "commit", "oid": commit},
            "tree": {"algorithm": "repository-default", "object_type": "tree", "oid": tree},
        },
        "changed_paths": sorted(set(path.replace("\\", "/") for path in changed_paths)),
        # W07: an escalation to every gate is a decision, and a decision has to name its cause. Without this
        # the plan read as "run everything" with nothing to act on; the fix (declare the path under a module
        # root, or under risk_zones.critical if it is genuinely sensitive) was not discoverable from the plan.
        "unclassified_paths": [
            {"path": path,
             "reason": "no module root and no gate pattern in .project/governance/work-lab.project-profile.yaml "
                       "selects this path",
             "needs": "declare it under the owning module's roots, or under risk_zones.critical when it is a "
                      "sensitive surface; until then every gate runs, which is correct but expensive"}
            for path in sorted(set(unknown_paths))
        ],
        "required_gates": required,
        # W07: the CI jobs these gates correspond to, so "what does this change require" has one answer
        # that names both sides. The mapping comes from the profile, which `verify_gate_ci_job_mapping.py`
        # checks against the workflows in both directions -- a suggestion here cannot silently miss a job.
        "ci_jobs": {gate_id: (gates.get(gate_id) or {}).get("ci_job") for gate_id in required},
        "skipped_gates": skipped,
        "risk": "critical" if critical else ("low" if not changed_paths else "medium"),
        "delivery_effect": delivery_effect,
        "platform_scope": sorted(set(platform_scope or ["discovered"])),
        "generated_at": generated_at,
    }
    payload["plan_digest"] = _digest(payload)
    schema = json.loads(SCHEMA.read_text(encoding="utf-8"))
    errors = list(Draft202012Validator(schema, format_checker=FormatChecker()).iter_errors(payload))
    if errors:
        raise ValueError(f"generated gate plan is invalid: {errors[0].message}")
    return payload


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--profile", type=Path, required=True)
    parser.add_argument("--repo", type=Path, default=Path.cwd())
    parser.add_argument("--repository", required=True)
    parser.add_argument("--commit")
    parser.add_argument("--tree")
    parser.add_argument("--changed-path", action="append", default=[])
    parser.add_argument("--delivery-effect", choices=("none", "commit", "push", "pull_request", "merge", "release"), default="none")
    parser.add_argument("--platform", action="append", dest="platform_scope")
    parser.add_argument("--plan-id", default="plan-local")
    parser.add_argument("--generated-at", default="2026-08-07T00:00:00Z")
    args = parser.parse_args()
    root = args.repo.resolve()
    commit = args.commit or _git(root, "rev-parse", "HEAD")
    tree = args.tree or _git(root, "rev-parse", "HEAD^{tree}")
    changed = args.changed_path or [path for path in _git(root, "diff", "--name-only", "HEAD^", "HEAD").splitlines() if path]
    plan = build_plan(load_profile(args.profile), repository=args.repository, commit=commit, tree=tree, changed_paths=changed, delivery_effect=args.delivery_effect, platform_scope=args.platform_scope, plan_id=args.plan_id, generated_at=args.generated_at)
    print("GATE_PLAN_PASS " + json.dumps({"plan_id": plan["plan_id"], "required_gates": plan["required_gates"], "skipped": len(plan["skipped_gates"]), "risk": plan["risk"], "digest": plan["plan_digest"]["value"]}, ensure_ascii=False, sort_keys=True))
    print(json.dumps(plan, ensure_ascii=False, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

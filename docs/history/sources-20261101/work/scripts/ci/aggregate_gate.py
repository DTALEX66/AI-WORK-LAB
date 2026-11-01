from __future__ import annotations

import fnmatch
import hashlib
import json
import sys
from datetime import datetime
from pathlib import Path

import yaml

REQUIRED = {"workflow", "observer", "token-monitor", "supply-chain-security", "integration"}
PLAN_GATES = {"workflow", "observer", "token-monitor", "supply-chain-security", "integration"}
JOB_NAMES = {
    "workflow": "workflow",
    "observer": "observer",
    "token-monitor": "token-monitor",
    "supply-chain-security": "supply-chain-security",
    "integration": "integration",
}
EXPECTED_PLAN_ID = "work-lab-gate"
ROOT = Path(__file__).resolve().parents[2]
PROFILE = ROOT / ".project/governance" / "work-lab.project-profile.yaml"
RISK_VALUES = {"low", "medium", "high", "critical"}
DELIVERY_VALUES = {"none", "commit", "push", "pull_request", "merge", "release"}


def _plan_digest(plan: dict[str, object]) -> str:
    payload = {key: value for key, value in plan.items() if key not in {"generated_at", "plan_id", "plan_digest"}}
    canonical = json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(canonical).hexdigest()


def _matches(path: str, patterns: list[str]) -> bool:
    normalized = path.replace("\\", "/")
    return any(
        fnmatch.fnmatch(normalized, pattern) or normalized.startswith(pattern.rstrip("*").rstrip("/"))
        for pattern in patterns
    )


def _load_critical_prefixes() -> list[str]:
    if not PROFILE.is_file():
        raise ValueError(f"project profile missing: {PROFILE}; cannot re-derive critical risk")
    data = yaml.safe_load(PROFILE.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise ValueError("project profile must be an object")
    prefixes = (data.get("risk_zones") or {}).get("critical")
    if not isinstance(prefixes, list) or not prefixes or not all(isinstance(p, str) and p for p in prefixes):
        raise ValueError("project profile risk_zones.critical must be a non-empty string list")
    return prefixes


def _is_critical(changed_paths: list[str]) -> bool:
    """A6: re-derive critical risk from the profile's risk_zones, never trust
    the plan's own risk field, so a candidate cannot evade full gates by
    editing the planner."""
    prefixes = _load_critical_prefixes()
    return any(_matches(path, prefixes) for path in changed_paths)


def _resolve_plan(data: dict[str, object]) -> tuple[set[str], str, str, str, str, list[str]]:
    raw_plan = data.get("gate_plan")
    if raw_plan is None:
        raise ValueError("gate_plan is required")
    if not isinstance(raw_plan, dict):
        raise ValueError("gate_plan must be an object")
    if raw_plan.get("schema_version") != "workflow/gate-plan/v1":
        raise ValueError("gate_plan schema_version must be workflow/gate-plan/v1")
    if raw_plan.get("plan_id") != EXPECTED_PLAN_ID:
        raise ValueError(f"gate_plan plan_id must be {EXPECTED_PLAN_ID}")
    required = raw_plan.get("required_gates")
    changed_paths = raw_plan.get("changed_paths")
    digest = raw_plan.get("plan_digest")
    source_identity = raw_plan.get("source_identity")
    skipped = raw_plan.get("skipped_gates")
    risk = raw_plan.get("risk")
    delivery_effect = raw_plan.get("delivery_effect")
    platform_scope = raw_plan.get("platform_scope")
    generated_at = raw_plan.get("generated_at")
    if not isinstance(required, list) or not all(isinstance(item, str) for item in required):
        raise ValueError("gate_plan.required_gates must be a string list")
    if len(required) != len(set(required)):
        raise ValueError("gate_plan.required_gates must be unique")
    if not isinstance(changed_paths, list) or not all(isinstance(item, str) and item for item in changed_paths):
        raise ValueError("gate_plan.changed_paths must be a non-empty-string list")
    normalized_required = set(required)
    unknown = normalized_required - PLAN_GATES
    if unknown:
        raise ValueError(f"gate_plan contains unknown gates: {sorted(unknown)}")
    if changed_paths and not normalized_required:
        raise ValueError("gate_plan with changed paths must require at least one gate")
    if (
        not isinstance(digest, dict)
        or digest.get("algorithm") != "sha256"
        or not isinstance(digest.get("value"), str)
    ):
        raise ValueError("gate_plan.plan_digest must be sha256")
    computed = _plan_digest(raw_plan)
    if digest["value"] != computed:
        raise ValueError("gate_plan digest mismatch")
    if not isinstance(source_identity, dict):
        raise ValueError("gate_plan.source_identity must be an object")
    repository = source_identity.get("repository")
    commit_identity = source_identity.get("commit")
    tree_identity = source_identity.get("tree")
    if not isinstance(repository, str) or not repository:
        raise ValueError("gate_plan source repository is required")
    if not isinstance(commit_identity, dict) or not isinstance(commit_identity.get("oid"), str) or not commit_identity["oid"]:
        raise ValueError("gate_plan source commit oid is required")
    if not isinstance(tree_identity, dict) or not isinstance(tree_identity.get("oid"), str) or not tree_identity["oid"]:
        raise ValueError("gate_plan source tree oid is required")
    commit = commit_identity["oid"]
    tree = tree_identity["oid"]
    if not isinstance(skipped, list) or not all(isinstance(item, dict) for item in skipped):
        raise ValueError("gate_plan.skipped_gates must be an object list")
    skipped_ids: set[str] = set()
    for item in skipped:
        gate_id = item.get("gate_id")
        reason = item.get("reason")
        if not isinstance(gate_id, str) or not gate_id:
            raise ValueError("gate_plan skipped_gates[].gate_id is required")
        if not isinstance(reason, str) or not reason:
            raise ValueError("gate_plan skipped_gates[].reason is required")
        skipped_ids.add(gate_id)
    if skipped_ids != PLAN_GATES - normalized_required:
        missing = sorted((PLAN_GATES - normalized_required) - skipped_ids)
        raise ValueError(f"skipped_gates must cover exactly the non-required gates; missing: {missing}")
    if risk not in RISK_VALUES:
        raise ValueError(f"gate_plan.risk must be one of {sorted(RISK_VALUES)}")
    if delivery_effect not in DELIVERY_VALUES:
        raise ValueError(f"gate_plan.delivery_effect must be one of {sorted(DELIVERY_VALUES)}")
    if (
        not isinstance(platform_scope, list)
        or not platform_scope
        or len(platform_scope) != len(set(platform_scope))
        or not all(isinstance(item, str) and item for item in platform_scope)
    ):
        raise ValueError("gate_plan.platform_scope must be a non-empty unique string list")
    if not isinstance(generated_at, str) or not generated_at:
        raise ValueError("gate_plan.generated_at is required")
    try:
        datetime.fromisoformat(generated_at.replace("Z", "+00:00"))
    except ValueError:
        raise ValueError("gate_plan.generated_at must be ISO8601")
    if _is_critical(changed_paths) and normalized_required != PLAN_GATES:
        raise ValueError("critical changed paths require ALL gates; plan under-selects")
    return normalized_required, digest["value"], commit, tree, repository, sorted(changed_paths)


def _fail(reason: str, digest: str | None) -> int:
    result: dict[str, object] = {"status": "FAIL", "reason": reason}
    if digest is not None:
        result["plan_digest"] = digest
    print(json.dumps(result, ensure_ascii=False, sort_keys=True))
    return 1


def main(payload: str) -> int:
    try:
        data = json.loads(payload)
        if not isinstance(data, dict):
            raise ValueError("aggregate payload must be an object")
        required, digest, plan_commit, plan_tree, plan_repository, _ = _resolve_plan(data)
        expected_digest = data.get("expected_plan_digest")
        if not isinstance(expected_digest, str) or not expected_digest:
            raise ValueError("aggregate expected plan digest is required")
        if expected_digest != digest:
            raise ValueError("aggregate expected plan digest does not match plan")
        expected_commit = data.get("expected_head_sha")
        if not isinstance(expected_commit, str) or not expected_commit:
            raise ValueError("aggregate expected head SHA is required")
        if expected_commit != plan_commit:
            raise ValueError("aggregate plan commit does not match head SHA")
        expected_tree = data.get("expected_head_tree")
        if not isinstance(expected_tree, str) or not expected_tree:
            raise ValueError("aggregate expected head tree is required")
        if expected_tree != plan_tree:
            raise ValueError("aggregate plan tree does not match head tree")
        expected_repository = data.get("expected_repository")
        if not isinstance(expected_repository, str) or not expected_repository:
            raise ValueError("aggregate expected repository is required")
        if expected_repository != plan_repository:
            raise ValueError("aggregate plan repository does not match expected repository")
        jobs = data.get("jobs", {})
        if not isinstance(jobs, dict):
            raise ValueError("aggregate jobs must be an object")
        bad = [JOB_NAMES[name] for name in required if jobs.get(JOB_NAMES[name]) not in {"success", "passed"}]
        if bad:
            return _fail(f"required job(s) missing or failed: {sorted(bad)}", digest)
        not_required = PLAN_GATES - required
        not_skipped = [JOB_NAMES[name] for name in not_required if jobs.get(JOB_NAMES[name]) != "skipped"]
        if not_skipped:
            return _fail(f"non-selected gate(s) not explicitly skipped: {sorted(not_skipped)}", digest)
        result: dict[str, object] = {
            "status": "PASS",
            "required": sorted(JOB_NAMES[name] for name in required),
            "skipped": sorted(JOB_NAMES[name] for name in not_required),
        }
        result["plan_digest"] = digest
        print(json.dumps(result, ensure_ascii=False, sort_keys=True))
        return 0
    except (ValueError, TypeError, json.JSONDecodeError) as exc:
        print(json.dumps({"status": "FAIL", "reason": str(exc)}, ensure_ascii=False, sort_keys=True))
        return 1


if __name__ == "__main__":
    raise SystemExit(main(sys.stdin.read()))

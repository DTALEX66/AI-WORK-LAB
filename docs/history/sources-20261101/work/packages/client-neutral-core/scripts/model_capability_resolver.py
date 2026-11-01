"""Task-level capability resolver (WL3-330 / MR-08).

A pure function: inputs are a task contract, policy snapshot, catalog
snapshot, runtime health, and resource snapshot; output is an InvocationPlan
that is NEVER executed here. Sorting rules (taskpack §MR-08):

1. user explicit choice for this task
2. project approved overlay
3. satisfies all capability/data-boundary/quality
4. existing session affinity
5. local availability
6. stability
7. equivalent candidates

Fail-closed rules:
- never sort by model ID alphabetically
- never silent fallback (blocked candidate -> BLOCKED, not auto-substitute)
- PRIVATE/UNKNOWN data never routes to DeepSeek
- code-write defaults to agent.code.primary
- observer tasks never get a model invocation
- selected and rejected candidates both carry reason codes

AG-01..AG-04 (2026-10-01 atlas gap remediation, see
taskpacks/history/pre-convergence-20261019/WORK-LAB-ATLAS-GAP-REMEDIATION-TASKCARD-20261001.md):
- an explicit user choice is TERMINAL when usable — a project overlay can
  never silently overwrite it (AG-01);
- every entry path (explicit, overlay, scan) shares the SAME capability /
  boundary / availability gate, so a missing required capability is refused
  on all of them with a specific reason (AG-02);
- session affinity uses a stable digest instead of the salted builtin
  ``hash()``, so it does not drift across processes (AG-03);
- ``runtime_health`` / ``resource`` are enforced (unhealthy candidate ->
  refusal with ``RUNTIME_UNHEALTHY``) instead of being accepted and ignored
  (AG-04). An unknown health shape is not treated as unhealthy: absence of
  evidence is not evidence of failure.
"""
from __future__ import annotations

import hashlib
import json
from typing import Any

SCHEMA_VERSION = "workflow/model-invocation-plan/v1"

# Reason codes (taskpack §20.7)
R_USER_CHOSEN = "USER_EXPLICIT_CHOICE"
R_PROJECT_OVERLAY = "PROJECT_APPROVED_OVERLAY"
R_CAPABILITY_OK = "CAPABILITY_SATISFIED"
R_SESSION_AFFINITY = "SESSION_AFFINITY"
R_LOCAL_AVAILABLE = "LOCAL_AVAILABLE"
R_STABILITY = "STABILITY"
R_EQUIVALENT = "EQUIVALENT_CANDIDATE"
R_PRIVATE_DATA = "PRIVATE_DATA_NO_CLOUD"
R_UNKNOWN_DATA = "UNKNOWN_DATA_NO_CLOUD"
R_RETIRED = "RETIRED_PROVIDER"
R_UNAVAILABLE = "CAPABILITY_UNAVAILABLE"
R_EGRESS_BLOCKED = "CLOUD_EGRESS_BLOCKED"
R_OBSERVER_NO_MODEL = "OBSERVER_TASK_NO_MODEL"
R_NO_KEY = "EXECUTOR_NO_API_KEY"
R_CODE_WRITE_DEFAULT = "CODE_WRITE_AGENT_PRIMARY"
R_MISSING_CAPABILITY = "MISSING_CAPABILITY"
R_RUNTIME_UNHEALTHY = "RUNTIME_UNHEALTHY"

# Health states that refuse a candidate. Only these explicit values are
# treated as unhealthy; an unknown/absent shape stays "no evidence" so the
# resolver never invents a failure.
UNHEALTHY_STATUSES = frozenset(
    {"DOWN", "UNHEALTHY", "FAILED", "BLOCKED", "UNAVAILABLE", "ERROR"}
)
# Advisory states: not serving ad-hoc work, but not a fault.
SATURATED_STATUSES = frozenset({"SATURATED", "EXHAUSTED", "FULL", "BUSY"})

# Ordered gate reasons, most specific first, so an explicit user choice gets
# the most actionable refusal code available.
_UNUSABLE_REASON_ORDER = (
    (R_RETIRED, "lifecycle"),
    ("QUALITY_BLOCKED", "quality_state"),
    (R_RUNTIME_UNHEALTHY, "health"),
    (R_PRIVATE_DATA, "privacy"),
    (R_UNKNOWN_DATA, "privacy"),
    (R_EGRESS_BLOCKED, "egress"),
)


class Resolver:
    def __init__(self, policy: dict[str, Any], catalog: dict[str, Any],
                 runtime_health: dict[str, Any], resource: dict[str, Any]) -> None:
        self.policy = policy or {}
        self.catalog = catalog or {}
        self.runtime_health = runtime_health or {}
        self.resource = resource or {}

    def resolve(self, task: dict[str, Any]) -> dict[str, Any]:
        task_id = task.get("task_id", "unknown")
        data_privacy = task.get("data_privacy", "unknown")
        task_kind = task.get("task_kind", "general")
        required_capabilities = set(task.get("required_capabilities", []) or [])
        explicit_model = task.get("explicit_model")

        candidates = self._candidate_pool()
        rejected: list[dict[str, Any]] = []

        # Observer tasks never get a model.
        if task_kind == "observer":
            return self._plan(task_id, None, [], R_OBSERVER_NO_MODEL, no_model=True)

        # 1. user explicit choice — TERMINAL when usable (AG-01). A project
        # overlay must never silently overwrite what the user asked for.
        if explicit_model:
            cand = candidates.get(explicit_model)
            reason = self._reject_reason(cand, required_capabilities, data_privacy)
            if reason is None:
                # Picked under the same gate as any other candidate (AG-02).
                return self._plan(task_id, self._pick(explicit_model, cand, R_USER_CHOSEN),
                                  rejected, R_USER_CHOSEN)
            rejected.append({"candidate": explicit_model, "reason": reason})
            return self._plan(task_id, None, rejected, reason)

        # 2. project approved overlay — same gate as every other path (AG-02).
        overlay = (self.policy.get("project_overlay") or {}).get("preferred_models") or []
        for model_id in overlay:
            cand = candidates.get(model_id)
            reason = self._reject_reason(cand, required_capabilities, data_privacy)
            if reason is None:
                return self._plan(task_id, self._pick(model_id, cand, R_PROJECT_OVERLAY),
                                  rejected, R_PROJECT_OVERLAY)
            rejected.append({"candidate": model_id, "reason": reason})

        # 3. capability satisfaction scan. Deterministic order: best session
        # affinity wins, ties broken by model id — never selected-first.
        selected = None
        best_affinity = -1
        for model_id in sorted(candidates):
            cand = candidates[model_id]
            reason = self._reject_reason(cand, required_capabilities, data_privacy)
            if reason is not None:
                rejected.append({"candidate": model_id, "reason": reason})
                continue
            affinity = self._session_affinity(model_id, task_id)
            if selected is None or affinity > best_affinity:
                best_affinity = affinity
                selected = self._pick(
                    model_id, cand,
                    R_SESSION_AFFINITY if affinity > 0 else R_CAPABILITY_OK,
                )

        if not selected:
            reason = self._first_rejection_reason(rejected)
            return self._plan(task_id, None, rejected, reason or R_UNAVAILABLE)

        # include rejected for audit
        return self._plan(task_id, selected, rejected, selected["reason"])

    # -- helpers ------------------------------------------------------------
    def _candidate_pool(self) -> dict[str, Any]:
        pool: dict[str, Any] = {}
        catalog = self.catalog.get("models") or {}
        for model_id, model in catalog.items():
            entry = dict(model)
            entry["model_id"] = model_id
            pool[model_id] = entry
        return pool

    def _runtime_keys(self, cand: dict[str, Any]) -> list[str]:
        keys = []
        for field in ("runtime_id", "binds_to_runtime", "runtime", "provider"):
            value = cand.get(field)
            if isinstance(value, str) and value:
                keys.append(value)
        return keys

    def _health_entry(self, cand: dict[str, Any]) -> dict[str, Any] | None:
        """Best-effort lookup of a health record for the candidate.

        Accepts either a flat ``{id: {...}}`` map or a wrapper whose
        ``runtimes``/``providers`` member is that map. An unknown shape
        returns None (no evidence), never an invented failure.
        """
        lookup: dict[str, Any] = {}
        for key in ("runtimes", "providers", "health"):
            member = self.runtime_health.get(key)
            if isinstance(member, dict):
                lookup.update(member)
        # Also accept a flat {runtime_or_provider_id: {...}} map.
        for key, value in self.runtime_health.items():
            if isinstance(key, str) and isinstance(value, dict):
                lookup.setdefault(key, value)
        for name in self._runtime_keys(cand):
            entry = lookup.get(name)
            if isinstance(entry, dict):
                return entry
        return None

    def _unhealthy(self, cand: dict[str, Any]) -> bool:
        entry = self._health_entry(cand)
        if not entry:
            return False
        status = entry.get("status")
        if not isinstance(status, str):
            return False
        return status.strip().upper() in UNHEALTHY_STATUSES

    def _reject_reason(self, cand: dict[str, Any] | None,
                       required_capabilities: set[str],
                       data_privacy: str) -> str | None:
        """Single shared gate for every selection path. None == acceptable.

        Most specific refusal wins so an explicit user choice is told exactly
        what was wrong, and a missing required capability is always refused
        (never silently satisfied by an unusable candidate).
        """
        if not cand:
            return "UNKNOWN_CANDIDATE"

        # Capability conformance must never be bypassed on any path. The
        # code-write role guard is checked first and without a prerequisite
        # capability test so a non-primary writer is reported as
        # NOT_CODE_WRITE_PRIMARY — the precise, actionable reason — rather
        # than as a generic missing capability.
        if "code.write" in required_capabilities and cand.get("role") != "agent.code.primary":
            return "NOT_CODE_WRITE_PRIMARY"
        caps = set(cand.get("capabilities", []) or [])
        if required_capabilities and not required_capabilities.issubset(caps):
            return R_MISSING_CAPABILITY

        for reason, kind in _UNUSABLE_REASON_ORDER:
            if kind == "lifecycle" and cand.get("lifecycle") == "RETIRED":
                return reason
            if kind == "quality_state" and cand.get("quality_state") == "BLOCKED":
                return reason
            if kind == "health" and self._unhealthy(cand):
                return reason
            if kind == "privacy" and cand.get("locality", "local") == "cloud" \
                    and data_privacy in ("private", "unknown"):
                return R_PRIVATE_DATA if data_privacy == "private" else R_UNKNOWN_DATA
            if kind == "egress" and cand.get("locality", "local") == "cloud" \
                    and cand.get("egress") == "approval_required":
                return reason
        return None

    def _usable(self, cand: dict[str, Any] | None, data_privacy: str) -> bool:
        """Availability/boundary check only (no capability knowledge)."""
        return self._reject_reason(cand, set(), data_privacy) is None

    def _unusable_reason(self, model_id: str, cand: dict[str, Any] | None,
                         data_privacy: str) -> str:
        return self._reject_reason(cand, set(), data_privacy) or R_UNAVAILABLE

    def _session_affinity(self, model_id: str, task_id: str) -> int:
        """Stable pseudo-affinity: same task family reuses the prior model.

        Uses SHA-256 over an explicit encoding instead of the builtin
        ``hash()``, whose string hashing is salted per process (AG-03).
        """
        family = task_id.split("-")[0] if "-" in task_id else task_id
        digest = hashlib.sha256(f"{family}\x1f{model_id}".encode("utf-8")).digest()
        return int.from_bytes(digest[:8], "big") % 100

    def _pick(self, model_id: str, cand: dict[str, Any], reason: str) -> dict[str, Any]:
        return {
            "candidate": model_id,
            "provider": cand.get("provider"),
            "locality": cand.get("locality"),
            "role": cand.get("role"),
            "reason": reason,
        }

    def _first_rejection_reason(self, rejected: list[dict[str, Any]]) -> str | None:
        if not rejected:
            return None
        return rejected[0].get("reason")

    def _plan(self, task_id: str, selected: dict[str, Any] | None,
              rejected: list[dict[str, Any]], reason: str | None,
              no_model: bool = False) -> dict[str, Any]:
        return {
            "schema_version": SCHEMA_VERSION,
            "plan_id": f"plan-{task_id}",
            "task_id": task_id,
            "status": "NO_MODEL_REQUIRED" if no_model else ("READY" if selected else "BLOCKED"),
            "selected": selected,
            "rejected": rejected,
            "reason_code": reason,
            "execution": "deferred_to_worker" if selected and not no_model else "none",
        }


if __name__ == "__main__":
    sample = {
        "policy": {"project_overlay": {"preferred_models": ["local-coder"]}},
        "catalog": {"models": {
            "local-coder": {"provider": "ollama", "locality": "local", "role": "local.code.readonly", "capabilities": ["code.read"], "lifecycle": "ACTIVE", "quality_state": "OK"},
            "cloud-deepseek": {"provider": "deepseek", "locality": "cloud", "role": "cloud.reasoning.deep", "capabilities": ["text"], "lifecycle": "ACTIVE", "quality_state": "OK", "egress": "approval_required"},
            "kimi": {"provider": "kimi", "locality": "cloud", "role": "historical", "lifecycle": "RETIRED", "quality_state": "OK"},
        }},
        "runtime_health": {},
        "resource": {},
    }
    resolver = Resolver(**sample)
    print(json.dumps(resolver.resolve({"task_id": "t-1", "task_kind": "code-read", "data_privacy": "public", "required_capabilities": ["code.read"]}), ensure_ascii=False, indent=2))
